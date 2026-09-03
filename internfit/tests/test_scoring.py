import unittest

from core.cv_parser import CandidateProfile, _profile_from_lines
from core.sample_jobs import SAMPLE_JOBS
from core.job_parser import JobPosting
from core.scoring import _domain_score_cap, assess_fit


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
        self.assertEqual(ing.recommendation, "Lower priority")

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

    def test_missing_role_specific_domain_is_capped(self):
        job = JobPosting(
            title="Software Engineering Intern",
            company="Example",
            url="",
            text=(
                "Build backend APIs and write production Python. "
                "Requirements: computer science degree and software engineering experience."
            ),
        )
        result = assess_fit(self.candidate, job)
        self.assertLessEqual(result.score, 72)
        cap, reason = _domain_score_cap(self.candidate, {"software_engineering"})
        self.assertEqual(cap, 72)
        self.assertIn("software engineering", reason)

    def test_graduation_detection_is_not_bba_specific(self):
        candidate = _profile_from_lines(
            ["Bachelor of Arts Candidate, Class of 2027", "Example University"],
            "friend.docx",
        )
        self.assertEqual(candidate.graduation, "Bachelor of Arts Candidate, Class of 2027")

    def test_related_business_degree_is_not_bba_specific(self):
        candidate = _profile_from_lines(
            ["Bachelor of Science in Management, Class of 2027", "Example University"],
            "friend.docx",
        )
        job = JobPosting(
            title="Business Intern",
            company="Example",
            url="",
            text="Requirements: business degree and current student status.",
        )
        result = assess_fit(candidate, job)
        self.assertNotIn("missing qualification: business_degree", result.gaps)

    def test_minimum_graduate_technical_degree_is_a_hard_gate(self):
        job = JobPosting(
            title="AI Integration Intern",
            company="Example",
            url="",
            text=(
                "Role Overview\nBuild an MCP server and integrate tools.\n"
                "Minimum Qualification\nCurrently enrolled in a MS or PhD degree program "
                "in computer science, computer engineering, electrical engineering, or a related field.\n"
                "Preferred Qualifications\nPython, REST API, LLM and MCP."
            ),
        )
        result = assess_fit(self.candidate, job)
        self.assertEqual(result.eligibility, "Risk")
        self.assertIn("Required graduate technical degree missing", result.blockers)
        self.assertLessEqual(result.score, 45)
        self.assertIn("missing qualification: graduate_technical_degree", result.gaps)
        self.assertTrue(any("minimum qualification" in detail for detail in result.gap_details))

    def test_preferred_technical_degree_is_not_a_hard_gate(self):
        candidate = _profile_from_lines(
            ["B.B.A. Candidate, Class of 2027", "Example University"],
            "friend.docx",
        )
        job = JobPosting(
            title="Digital Intern",
            company="Example",
            url="",
            text="Responsibilities: support digital projects. Preferred Qualifications: MS in computer science preferred.",
        )
        result = assess_fit(candidate, job)
        self.assertEqual(result.eligibility, "Pass")
        self.assertNotIn("Required graduate technical degree missing", result.blockers)

    def test_graduate_technical_candidate_can_pass_degree_gate(self):
        candidate = _profile_from_lines(
            ["M.S. Computer Science, Currently enrolled, Class of 2027", "Example University"],
            "technical_candidate.docx",
        )
        job = JobPosting(
            title="AI Integration Intern",
            company="Example",
            url="",
            text="Minimum Qualification: Currently enrolled in a MS or PhD degree program in computer science.",
        )
        result = assess_fit(candidate, job)
        self.assertNotIn("Required graduate technical degree missing", result.blockers)


if __name__ == "__main__":
    unittest.main()
