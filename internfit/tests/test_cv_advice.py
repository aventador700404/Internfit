import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from core.analysis_trace import build_evidence_trace, build_trace_summary
from core.cv_parser import _profile_from_lines
from core.job_parser import JobPosting
from core.llm_client import (
    MAX_CV_CHARS, MAX_SOURCE_CHARS, OMISSION_MARKER, LunaResult,
    _build_sources, _validated_semantic, analyze_with_luna,
)
from core.scoring import assess_fit


def fixtures():
    candidate = _profile_from_lines([
        "경영학과 재학 / 한국어, 영어",
        "시장조사 프로젝트에서 경쟁사 12곳의 제품과 가격을 비교하고 보고서를 작성했습니다.",
    ], "test-only.docx")
    job = JobPosting(title="Research Intern", company="Example", url="",
        text="Analyze competitor pricing and explain the resulting business recommendations.")
    suggestion = "공고는 분석에 따른 제안을 요구합니다. 경쟁사 12곳을 비교한 경험에 어떤 기준으로 판단했고 보고서가 어떤 결정에 쓰였는지 실제 사실을 추가하세요."
    gap = {"tag": "research", "edit_type": "clarify_existing", "job_source_id": "J001",
           "cv_source_id": "C001", "suggestion": suggestion}
    return candidate, job, gap


class CvAdviceTests(unittest.TestCase):
    def test_cross_language_advice_resolves_real_sources_and_reaches_result(self):
        candidate, job, gap = fixtures()
        # Even unexpected retyped text cannot replace the server-owned source.
        raw = {"gaps": [dict(gap, job_evidence="invented requirement")]}
        diagnostics = []
        semantic = _validated_semantic(raw, candidate, job, diagnostics)
        sources = _build_sources(candidate, job)
        accepted = semantic["gaps"][0]
        self.assertEqual(accepted["job_evidence"], sources["job"]["J001"])
        self.assertEqual(accepted["cv_evidence"], sources["cv"]["C001"])
        self.assertEqual(diagnostics[0]["reason"], "source_reference_verified")
        result = assess_fit(candidate, job, semantic=semantic)
        self.assertIn(gap["suggestion"], result.gap_details)
        self.assertNotIn("invented requirement", json.dumps(semantic))

    def test_unknown_or_wrong_document_references_fail_per_item(self):
        candidate, job, gap = fixtures()
        cases = [
            ({"job_source_id": "J999"}, "unknown_job_source_id"),
            ({"job_source_id": "C001"}, "unknown_job_source_id"),
            ({"cv_source_id": "J001"}, "unknown_cv_source_id"),
            ({"cv_source_id": ""}, "existing_edit_requires_cv_source"),
            ({"edit_type": "invent_experience"}, "invalid_edit_type"),
        ]
        for changes, reason in cases:
            diagnostics = []
            semantic = _validated_semantic({"gaps": [dict(gap, **changes), gap]}, candidate, job, diagnostics)
            self.assertEqual(len(semantic["gaps"]), 1)
            self.assertEqual(diagnostics[0]["reason"], reason)
            self.assertEqual(diagnostics[1]["status"], "accepted")

    def test_missing_evidence_advice_can_be_conditional_without_cv_quote(self):
        candidate, job, gap = fixtures()
        missing = dict(gap, edit_type="evidence_to_add", cv_source_id="",
            suggestion="If you have used research to recommend a pricing decision, add that example and your role; the CV does not currently show it.")
        semantic = _validated_semantic({"gaps": [missing]}, candidate, job)
        self.assertEqual(semantic["gaps"][0]["cv_evidence"], "")
        self.assertEqual(semantic["gaps"][0]["edit_type"], "evidence_to_add")

    def test_source_sections_are_bounded_original_slices_without_omission_markers(self):
        candidate, job, _ = fixtures()
        candidate.raw_text = ("한국어 English source line with enough content.\n" * 700)
        sources = _build_sources(candidate, job)
        self.assertLessEqual(sum(map(len, sources["cv"].values())), MAX_CV_CHARS)
        self.assertTrue(all(0 < len(text) <= MAX_SOURCE_CHARS for text in sources["cv"].values()))
        self.assertTrue(all(text in candidate.raw_text for text in sources["cv"].values()))
        self.assertNotIn(OMISSION_MARKER, "".join(sources["cv"].values()))

    def test_one_request_constrains_ids_to_sections_actually_sent(self):
        candidate, job, gap = fixtures()
        raw = {"job_core_responsibility_tags": ["research"], "job_core_domain_tags": [],
               "job_preferred_tags": [], "job_preferred_domain_tags": [],
               "job_required_tools": [], "job_preferred_tools": [],
               "candidate_evidence": [], "matches": [], "gaps": [gap]}
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"output_text": json.dumps(raw)}).encode()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-key"}, clear=True), \
             patch("core.llm_client.reserve_luna_budget", return_value=SimpleNamespace(allowed=True, estimated_cost_usd=0.005, mode="test")), \
             patch("core.llm_client.urlopen", return_value=response) as request:
            result = analyze_with_luna(candidate, job, "test-only")
        request.assert_called_once()
        payload = json.loads(request.call_args.args[0].data)
        gap_schema = payload["text"]["format"]["schema"]["properties"]["gaps"]["items"]["properties"]
        self.assertEqual(gap_schema["job_source_id"]["enum"], ["J001"])
        self.assertEqual(gap_schema["cv_source_id"]["enum"], ["", "C001"])
        self.assertIn("[J001]", payload["input"][1]["content"][0]["text"])
        self.assertEqual(result.semantic["gaps"][0]["suggestion"], gap["suggestion"])

    def test_rejection_status_and_qualification_guidance_remain_visible(self):
        candidate, job, gap = fixtures()
        job.requirements = {"core_checks": {"graduate_technical_degree", "student"}}
        for source_id, expected_source, expected_status in (("J001", "llm", "accepted"), ("J999", "rule_based", "all_rejected")):
            validation = []
            semantic = _validated_semantic({"gaps": [dict(gap, job_source_id=source_id)]}, candidate, job, validation)
            luna = LunaResult(status="used", used=True, semantic=semantic, validation=validation)
            before, after = {}, {}
            baseline = assess_fit(candidate, job, diagnostics=before)
            result = assess_fit(candidate, job, semantic=semantic, diagnostics=after)
            summary = build_trace_summary(candidate, job, luna, baseline, result, before, after)
            self.assertEqual(summary["cv_advice_source"], expected_source)
            self.assertEqual(summary["llm_gap_status"], expected_status)
            self.assertIn("Required graduate technical degree missing", result.blockers)
            self.assertTrue(any("degree" in text.lower() for text in result.gap_details))
            self.assertEqual(result.score, baseline.score)
            trace = build_evidence_trace(candidate, job, luna, result, after)
            if source_id == "J001":
                self.assertEqual(trace["llm_gaps"][0]["job_source_id"], "J001")
                self.assertIn(gap["suggestion"], trace["displayed_gaps"])


if __name__ == "__main__":
    unittest.main()
