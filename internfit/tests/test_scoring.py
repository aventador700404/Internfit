import unittest

from core.cv_parser import CandidateProfile
from core.sample_jobs import SAMPLE_JOBS
from core.scoring import assess_fit


class FitScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = CandidateProfile(
            source_name="test_candidate.docx",
            raw_text="B.B.A Candidate. English C1. Excel PowerPoint Generative AI.",
            evidence={
                "strategy": ["Strategy project"],
                "research": ["Market research"],
                "operations": ["Operations coordination"],
                "stakeholder": ["Stakeholder communication"],
                "data_analysis": ["Data analysis"],
                "technology": ["Technology project"],
                "finance": ["M&A research"],
                "event_management": ["Event planning"],
            },
            languages={"korean", "english", "german"},
            tools={"excel", "powerpoint", "word", "ai_tools"},
            graduation="B.B.A. Candidate, Feb 2027",
            education=["Sungkyunkwan University"],
        )

    def test_sap_is_highest_fit(self):
        sap = assess_fit(self.candidate, SAMPLE_JOBS["SAP — Strategy & Operations Intern (high-fit expected)"])
        ing = assess_fit(self.candidate, SAMPLE_JOBS["ING — Debt Capital Markets Intern (mid-fit expected)"])
        self.assertGreater(sap.score, ing.score)
        self.assertEqual(sap.eligibility, "Pass")
        self.assertEqual(ing.recommendation, "Apply after targeted CV edits")

    def test_japanese_requirement_is_a_blocker(self):
        result = assess_fit(self.candidate, SAMPLE_JOBS["RLWRLD — AI & Robotics Strategy Intern, Japanese (eligibility fail expected)"])
        self.assertEqual(result.eligibility, "Risk")
        self.assertLessEqual(result.score, 55)
        self.assertTrue(any("eligibility gate" in detail for detail in result.gap_details))

    def test_short_terms_do_not_match_inside_unrelated_words(self):
        result = assess_fit(
            self.candidate,
            SAMPLE_JOBS["RLWRLD — AI & Robotics Strategy Intern, Japanese (eligibility fail expected)"],
        )
        self.assertNotIn("japanese", self.candidate.languages)
        self.assertNotEqual(result.score, 100)

    def test_explanations_are_unique_and_gap_guidance_is_actionable(self):
        result = assess_fit(self.candidate, SAMPLE_JOBS["ING — Debt Capital Markets Intern (mid-fit expected)"])
        self.assertTrue(result.match_explanations)
        self.assertEqual(
            len(result.match_explanations),
            len({explanation.casefold() for explanation in result.match_explanations}),
        )
        self.assertTrue(result.gap_details)
        self.assertTrue(any("capital-markets" in detail for detail in result.gap_details))

    def test_missing_specific_domain_is_penalized(self):
        job = SAMPLE_JOBS["RLWRLD — AI & Robotics Strategy Intern, Japanese (eligibility fail expected)"]
        result = assess_fit(self.candidate, job)
        self.assertLess(result.score, 60)
        self.assertTrue(any("robotics" in detail for detail in result.gap_details))


if __name__ == "__main__":
    unittest.main()
