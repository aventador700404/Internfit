import contextlib
from concurrent.futures import Future, ThreadPoolExecutor
import importlib.util
import io
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from docx import Document

from core.analysis_cache import AnalysisCache, AnalysisBusyError, analysis_cache_key
from core.analysis_trace import CONSENT_VERSION
from core.llm_client import LunaResult
from core.job_parser import JobPosting


def success():
    return LunaResult(status="used", used=True,
        semantic={"matches": [{"statement": "Specific, validated feedback."}]},
        input_tokens=210, output_tokens=90, estimated_cost_usd=0.003,
        budget_mode="supabase")


class AnalysisCacheTests(unittest.TestCase):
    def test_key_changes_with_content_and_analysis_configuration_not_filename(self):
        cv = SimpleNamespace(raw_text="English 한국어 CV", source_name="one.docx")
        job = SimpleNamespace(title="Intern", text="Research competitor prices.", url="https://example.com/one")
        key = analysis_cache_key(cv, job, model="luna", engine_version="v1")
        cv.source_name = "renamed.pdf"
        job.url = "https://example.com/two"
        self.assertEqual(key, analysis_cache_key(cv, job, model="luna", engine_version="v1"))
        for target, field in ((cv, "raw_text"), (job, "text"), (job, "title")):
            original = getattr(target, field)
            setattr(target, field, original + " changed")
            self.assertNotEqual(key, analysis_cache_key(cv, job, model="luna", engine_version="v1"))
            setattr(target, field, original)
        self.assertNotEqual(key, analysis_cache_key(cv, job, model="other", engine_version="v1"))
        self.assertNotEqual(key, analysis_cache_key(cv, job, model="luna", engine_version="v2"))
        for setting in ("PROMPT_VERSION", "VALIDATOR_VERSION"):
            with patch("core.analysis_cache." + setting, "new-version"):
                self.assertNotEqual(key, analysis_cache_key(cv, job, model="luna", engine_version="v1"))
        self.assertNotIn(cv.raw_text, key)

    def test_absolute_expiry_zero_reuse_cost_and_result_isolation(self):
        now = [0.0]
        cache = AnalysisCache(clock=lambda: now[0])
        compute = Mock(side_effect=success)
        first = cache.get_or_compute("same", compute)
        first.luna.semantic["matches"].clear()
        now[0] = 1799.0
        hit = cache.get_or_compute("same", compute)
        self.assertEqual((hit.status, hit.age_seconds), ("hit", 1799))
        self.assertEqual(len(hit.luna.semantic["matches"]), 1)
        self.assertEqual((hit.luna.status, hit.luna.budget_mode), ("cached", "cache"))
        self.assertEqual((hit.luna.input_tokens, hit.luna.output_tokens, hit.luna.estimated_cost_usd), (0, 0, 0))
        hit.luna.semantic["matches"].clear()
        self.assertEqual(len(cache.get_or_compute("same", compute).luna.semantic["matches"]), 1)
        now[0] = 1800.0
        cache.prune()
        self.assertEqual((len(cache._entries), cache._bytes), (0, 0))
        self.assertEqual(cache.get_or_compute("same", compute).status, "miss")
        self.assertEqual(compute.call_count, 2)

    def test_entry_and_byte_limits_evict_old_results(self):
        cache = AnalysisCache(max_entries=2)
        compute = Mock(side_effect=success)
        for key in ("a", "b", "a", "c", "b"):
            cache.get_or_compute(key, compute)
        self.assertEqual(compute.call_count, 4)
        self.assertEqual(len(cache._entries), 2)
        size = cache._bytes // 2
        bounded = AnalysisCache(max_bytes=size, max_entry_bytes=size)
        for key in ("a", "b", "a"):
            bounded.get_or_compute(key, compute)
        self.assertLessEqual(bounded._bytes, size)
        oversized = AnalysisCache(max_entry_bytes=1)
        compute.reset_mock()
        for _ in range(2):
            oversized.get_or_compute("a", compute)
        self.assertEqual(compute.call_count, 2)
        self.assertEqual(oversized._bytes, 0)

    def test_fallbacks_and_exceptions_do_not_poison_later_attempts(self):
        for status in ("disabled_no_key", "budget_exhausted", "api_error", "invalid_output"):
            cache = AnalysisCache()
            compute = Mock(side_effect=[LunaResult(status=status), success()])
            self.assertFalse(cache.get_or_compute("a", compute).luna.used)
            self.assertEqual(cache.get_or_compute("a", compute).status, "miss")
            self.assertEqual(cache.get_or_compute("a", compute).status, "hit")
            self.assertEqual(compute.call_count, 2)
        cache = AnalysisCache()
        compute = Mock(side_effect=[RuntimeError("test failure"), success()])
        with self.assertRaises(RuntimeError):
            cache.get_or_compute("a", compute)
        self.assertTrue(cache.get_or_compute("a", compute).luna.used)

    def test_six_simultaneous_requests_share_one_computation(self):
        started, release, waiting = threading.Event(), threading.Event(), threading.Event()
        lock = threading.Lock()
        waiter_count = [0]

        class ObservedFuture(Future):
            def result(self, timeout=None):
                with lock:
                    waiter_count[0] += 1
                    if waiter_count[0] == 5:
                        waiting.set()
                return super().result(timeout)

        def run():
            started.set()
            if not release.wait(5):
                raise TimeoutError("test producer was not released")
            return success()

        compute = Mock(side_effect=run)
        cache = AnalysisCache()
        with patch("core.analysis_cache.Future", ObservedFuture), ThreadPoolExecutor(max_workers=6) as pool:
            leader = pool.submit(cache.get_or_compute, "same", compute)
            self.assertTrue(started.wait(2))
            followers = [pool.submit(cache.get_or_compute, "same", compute) for _ in range(5)]
            try:
                self.assertTrue(waiting.wait(2))
            finally:
                release.set()
            results = [leader.result(2), *(f.result(2) for f in followers)]
        self.assertEqual(compute.call_count, 1)
        self.assertEqual([r.status for r in results], ["miss"] + ["shared"] * 5)
        self.assertTrue(all(r.luna.output_tokens == 0 for r in results[1:]))

    def test_wait_timeout_and_capacity_never_start_duplicate_calls(self):
        started, release = threading.Event(), threading.Event()
        def run():
            started.set()
            release.wait(5)
            return success()
        compute = Mock(side_effect=run)
        cache = AnalysisCache(max_inflight=1, wait_seconds=0)
        with ThreadPoolExecutor(max_workers=1) as pool:
            leader = pool.submit(cache.get_or_compute, "same", compute)
            self.assertTrue(started.wait(2))
            try:
                for key in ("same", "different"):
                    with self.assertRaises(AnalysisBusyError):
                        cache.get_or_compute(key, compute)
                self.assertEqual(compute.call_count, 1)
            finally:
                release.set()
            leader.result(2)
        self.assertEqual(cache.get_or_compute("same", compute).status, "hit")


CV_LINE = "Researched competitor pricing and wrote a market analysis report for the launch team."
JOB_TEXT = "Responsibilities: Research competitor prices and recommend business actions. Requirements: Enrolled undergraduate student with research and communication skills. Preferred: Experience presenting market analysis reports."


class ServerCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[2] / "internfit_web" / "server.py"
        spec = importlib.util.spec_from_file_location("internfit_cache_server", path)
        cls.server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.server)
        document = Document()
        for line in ("B.B.A. Candidate, Class of 2027", "English C1", CV_LINE):
            document.add_paragraph(line)
        file = io.BytesIO()
        document.save(file)
        cls.cv = file.getvalue()

    def request(self, sharing, filename="first.docx", url="https://example.com/job?a=1"):
        parts = [("cv", self.cv, filename), ("job_url", url.encode(), ""),
                 ("evidence_storage_consent", str(sharing).lower().encode(), ""),
                 ("consent_version", CONSENT_VERSION.encode(), "")]
        body = b""
        for name, value, file in parts:
            disposition = f'Content-Disposition: form-data; name="{name}"'
            if file:
                disposition += f'; filename="{file}"'
            body += b"--cache-boundary\r\n" + disposition.encode() + b"\r\n\r\n" + value + b"\r\n"
        body += b"--cache-boundary--\r\n"
        handler = object.__new__(self.server.AppHandler)
        handler.path = "/api/analyze"
        handler.headers = {"Content-Type": "multipart/form-data; boundary=cache-boundary", "Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler._json = MagicMock()
        handler.do_POST()
        self.assertEqual(handler._json.call_args.args[0], 200)
        return handler._json.call_args.args[1]

    def test_two_real_adapter_requests_call_provider_once_and_keep_current_consent(self):
        raw = {"job_core_responsibility_tags": ["research"],
            "candidate_evidence": [{"tag": "research", "strength": "direct", "evidence": CV_LINE}],
            "matches": [{"tag": "research", "statement": "The competitor-pricing report directly supports this role's research work.", "cv_evidence": CV_LINE}],
            "gaps": [{"tag": "research", "edit_type": "clarify_existing", "suggestion": "Clarify the decisions your competitor-pricing report informed, using an outcome you can support.", "job_source_id": "J001", "cv_source_id": "C001"}]}
        def fetch(url):
            return JobPosting(title="Research Intern", company="Test", url=url, text=JOB_TEXT, source_status="ok")
        for first_sharing in (False, True):
            with self.subTest(first_sharing=first_sharing):
                api = MagicMock()
                api.__enter__.return_value = api
                api.read.return_value = json.dumps({"output_text": json.dumps(raw), "usage": {"input_tokens": 210, "output_tokens": 90}}).encode()
                db = MagicMock()
                db.__enter__.return_value = db
                output = io.StringIO()
                with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only", "SUPABASE_URL": "https://example.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "test-only"}, clear=True), \
                     patch.object(self.server, "ANALYSIS_CACHE", AnalysisCache()), \
                     patch.object(self.server, "fetch_job_posting", side_effect=fetch) as fetched, \
                     patch("core.llm_client.reserve_luna_budget", return_value=SimpleNamespace(allowed=True, estimated_cost_usd=0.003, mode="test")) as reserve, \
                     patch("core.llm_client.urlopen", return_value=api) as provider, \
                     patch("core.telemetry_store.urlopen", return_value=db) as stored, \
                     contextlib.redirect_stdout(output):
                    first = self.request(first_sharing)
                    second = self.request(not first_sharing, filename="renamed.docx", url="https://example.com/job?a=2")
                    provider.assert_called_once()
                    reserve.assert_called_once()
                    self.assertEqual(fetched.call_count, 2)
                    self.assertEqual((first["llm_cache_status"], second["llm_cache_status"]), ("miss", "hit"))
                    self.assertEqual(first["score"], second["score"])
                    self.assertEqual(first["gap_details"], second["gap_details"])
                    self.assertNotIn("llm_failure_reason", first)
                    self.assertNotIn("llm_validation_summary", first)
                    self.assertNotEqual(first["analysis_id"], second["analysis_id"])
                    self.assertEqual(second["cv_name"], "renamed.docx")
                    self.assertEqual(second["apply_url"], "https://example.com/job?a=2")
                    rows = [json.loads(call.args[0].data)["payload"] for call in stored.call_args_list]
                    self.assertEqual(["analysis_trace" in row for row in rows], [first_sharing, not first_sharing])
                    self.assertEqual(second["evidence_storage_status"], "not_requested" if first_sharing else "stored")
                    for key in ("llm_input_tokens", "llm_output_tokens", "llm_estimated_cost_usd"):
                        self.assertGreater(rows[0][key], 0)
                        self.assertEqual(rows[1][key], 0)
                    self.assertEqual(rows[1]["llm_status"], "cached")
                    self.assertEqual(rows[1]["llm_cache_status"], "hit")
                    self.assertEqual(rows[1]["llm_validation_summary"], rows[0]["llm_validation_summary"])
                    self.assertEqual(rows[1]["llm_validation_summary"]["candidate_evidence"]["accepted"], 1)
                    os.environ.pop("OPENAI_API_KEY")
                    disabled = self.request(False)
                    self.assertEqual((disabled["llm_status"], disabled["llm_cache_status"]), ("disabled_no_key", "bypass"))
                    provider.assert_called_once()
                self.assertNotIn(CV_LINE, output.getvalue())


if __name__ == "__main__":
    unittest.main()
