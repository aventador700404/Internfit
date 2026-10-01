import json
import os
import unittest
from unittest.mock import MagicMock, patch

from core.cv_parser import CandidateProfile, _profile_from_lines
from core.job_parser import JobPosting
from core.llm_budget import reset_local_budget_for_tests
from core.llm_client import analyze_with_luna
from core.scoring import assess_fit


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return self.payload


def _candidate() -> CandidateProfile:
    return _profile_from_lines(
        [
            "B.B.A. Candidate, Class of 2027",
            "English C1",
            "Coordinated launch priorities with internal teams and tracked outcomes.",
        ],
        "semantic-candidate.docx",
    )


def _job() -> JobPosting:
    return JobPosting(
        title="Program Strategy Intern",
        company="Example",
        url="https://example.com/job",
        text="Responsibilities: Align cross-functional teams around launch priorities.",
    )


class LunaClientTests(unittest.TestCase):
    def setUp(self):
        reset_local_budget_for_tests()

    def tearDown(self):
        reset_local_budget_for_tests()

    def test_missing_key_keeps_llm_disabled(self):
        with patch.dict(os.environ, {}, clear=True), patch("core.llm_client.urlopen") as urlopen:
            result = analyze_with_luna(_candidate(), _job(), "analysis-no-key")

        self.assertEqual(result.status, "disabled_no_key")
        self.assertFalse(result.used)
        urlopen.assert_not_called()

    def test_valid_response_is_structured_and_source_validated(self):
        cv_quote = "Coordinated launch priorities with internal teams and tracked outcomes."
        job_quote = "Responsibilities: Align cross-functional teams around launch priorities."
        output = {
            "job_core_responsibility_tags": ["stakeholder"],
            "job_core_domain_tags": ["strategy"],
            "job_preferred_tags": [],
            "job_preferred_domain_tags": [],
            "job_required_tools": [],
            "job_preferred_tools": [],
            "candidate_evidence": [
                {"tag": "stakeholder", "strength": "supporting", "evidence": cv_quote},
                {"tag": "strategy", "strength": "direct", "evidence": "invented CV quote"},
            ],
            "matches": [
                {"tag": "stakeholder", "statement": "The CV shows cross-team coordination relevant to this role.", "cv_evidence": cv_quote},
                {"tag": "strategy", "statement": "This should be rejected because the quote is fake.", "cv_evidence": "invented CV quote"},
            ],
            "gaps": [
                {"tag": "strategy", "edit_type": "evidence_to_add", "suggestion": "If you have strategy experience, add the decision or outcome it produced.", "job_source_id": "J001", "cv_source_id": ""},
            ],
        }
        response = _FakeResponse({
            "output_text": json.dumps(output),
            "usage": {"input_tokens": 400, "output_tokens": 120},
        })
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-test-key"}, clear=True), patch(
            "core.llm_client.urlopen", return_value=response
        ) as urlopen:
            result = analyze_with_luna(_candidate(), _job(), "analysis-valid")

        self.assertTrue(result.used)
        self.assertEqual(result.status, "used")
        self.assertEqual(result.semantic["candidate"]["semantic_strengths"], {"stakeholder": 1})
        self.assertEqual(len(result.semantic["matches"]), 1)
        self.assertEqual(len(result.semantic["gaps"]), 1)

        request = urlopen.call_args.args[0]
        request_body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request_body["model"], "gpt-5.6-luna")
        self.assertFalse(request_body["store"])
        self.assertEqual(request_body["text"]["format"]["type"], "json_schema")
        self.assertNotIn(cv_quote, request_body["input"][0]["content"][0]["text"])
        self.assertIn(cv_quote, request_body["input"][1]["content"][0]["text"])

    def test_incomplete_response_logs_output_token_limit_reason(self):
        response = _FakeResponse({
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output_text": '{"candidate_evidence":[',
            "usage": {"input_tokens": 5500, "output_tokens": 1800},
        })
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-test-key"}, clear=True), patch(
            "core.llm_client.urlopen", return_value=response
        ):
            result = analyze_with_luna(_candidate(), _job(), "analysis-output-cap")

        self.assertEqual(result.status, "invalid_output")
        self.assertEqual(result.failure_stage, "api_response")
        self.assertEqual(result.failure_reason, "max_output_tokens")
        self.assertEqual(result.response_status, "incomplete")
        self.assertEqual(result.incomplete_reason, "max_output_tokens")
        self.assertEqual(result.output_tokens, 1800)

    def test_invalid_json_is_distinguished_from_provider_truncation(self):
        response = _FakeResponse({
            "status": "completed",
            "output_text": "not valid JSON",
            "usage": {"input_tokens": 100, "output_tokens": 25},
        })
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-test-key"}, clear=True), patch(
            "core.llm_client.urlopen", return_value=response
        ):
            result = analyze_with_luna(_candidate(), _job(), "analysis-invalid-json")

        self.assertEqual(result.status, "invalid_output")
        self.assertEqual(result.failure_stage, "json_parse")
        self.assertEqual(result.failure_reason, "invalid_json")
        self.assertEqual(result.response_status, "completed")

    def test_non_object_json_is_classified_as_semantic_validation_failure(self):
        response = _FakeResponse({"status": "completed", "output_text": "[]"})
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-test-key"}, clear=True), patch(
            "core.llm_client.urlopen", return_value=response
        ):
            result = analyze_with_luna(_candidate(), _job(), "analysis-not-object")

        self.assertEqual(result.status, "invalid_output")
        self.assertEqual(result.failure_stage, "semantic_validation")
        self.assertEqual(result.failure_reason, "root_not_object")

    def test_rejected_evidence_is_counted_without_logging_quote_text(self):
        rejected_quote = "This quote does not occur in the CV."
        output = {
            "job_core_responsibility_tags": [],
            "job_core_domain_tags": [],
            "job_preferred_tags": [],
            "job_preferred_domain_tags": [],
            "job_required_tools": [],
            "job_preferred_tools": [],
            "candidate_evidence": [
                {"tag": "stakeholder", "strength": "direct", "evidence": rejected_quote},
            ],
            "matches": [],
            "gaps": [],
        }
        response = _FakeResponse({"status": "completed", "output_text": json.dumps(output)})
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-test-key"}, clear=True), patch(
            "core.llm_client.urlopen", return_value=response
        ):
            result = analyze_with_luna(_candidate(), _job(), "analysis-rejected-evidence")

        self.assertTrue(result.used)
        self.assertEqual(
            result.validation_summary["candidate_evidence"],
            {
                "received": 1,
                "accepted": 0,
                "rejected": 1,
                "rejection_reasons": {"cv_quote_not_found_or_too_short": 1},
            },
        )
        self.assertNotIn(rejected_quote, json.dumps(result.validation_summary))

    def test_provider_failure_returns_fallback_status(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-test-key"}, clear=True), patch(
            "core.llm_client.urlopen", side_effect=OSError("network unavailable")
        ):
            result = analyze_with_luna(_candidate(), _job(), "analysis-error")

        self.assertEqual(result.status, "api_error")
        self.assertFalse(result.used)
        self.assertTrue(result.error_type)
        self.assertEqual(result.failure_stage, "api_request")
        self.assertEqual(result.failure_reason, "network_error")

    def test_budget_guard_blocks_before_provider_call(self):
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "server-test-key", "LLM_BUDGET_USD": "0.000001"},
            clear=True,
        ), patch("core.llm_client.urlopen") as urlopen:
            result = analyze_with_luna(_candidate(), _job(), "analysis-budget")

        self.assertEqual(result.status, "budget_exhausted")
        urlopen.assert_not_called()

    def test_semantic_overlay_improves_paraphrase_without_mutating_candidate(self):
        candidate = CandidateProfile(
            source_name="paraphrase.docx",
            raw_text="Coordinated launch priorities with internal teams and tracked outcomes.",
            evidence={"stakeholder": [], "strategy": []},
            languages={"english"},
            tools=set(),
            graduation=None,
            education=[],
        )
        job = _job()
        semantic = {
            "job": {
                "responsibility_tags": ["stakeholder"],
                "domain_tags": ["strategy"],
                "preferred_tags": [],
                "preferred_domain_tags": [],
                "required_tools": [],
                "preferred_tools": [],
            },
            "candidate": {
                "semantic_evidence": {"stakeholder": [candidate.raw_text]},
                "semantic_strengths": {"stakeholder": 1},
            },
            "matches": [{
                "tag": "stakeholder",
                "statement": "The CV shows cross-team coordination relevant to this role.",
                "cv_evidence": candidate.raw_text,
            }],
            "gaps": [],
        }

        baseline = assess_fit(candidate, job)
        assisted = assess_fit(candidate, job, semantic=semantic)

        self.assertGreater(assisted.score, baseline.score)
        self.assertEqual(assisted.match_explanations, [semantic["matches"][0]["statement"]])
        self.assertEqual(candidate.semantic_evidence, {})


if __name__ == "__main__":
    unittest.main()
