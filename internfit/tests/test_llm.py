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
                {"tag": "strategy", "suggestion": "Add the decision or outcome produced by the strategy work.", "job_evidence": job_quote, "cv_evidence": ""},
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

    def test_provider_failure_returns_fallback_status(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-test-key"}, clear=True), patch(
            "core.llm_client.urlopen", side_effect=OSError("network unavailable")
        ):
            result = analyze_with_luna(_candidate(), _job(), "analysis-error")

        self.assertEqual(result.status, "api_error")
        self.assertFalse(result.used)
        self.assertTrue(result.error_type)

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
