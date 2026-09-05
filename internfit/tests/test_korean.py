import unittest
from unittest.mock import patch

from core.cv_parser import _profile_from_lines, extract_pdf_bytes
from core.job_parser import JobPosting, fetch_job_posting, focus_job_content
from core.scoring import _split_preferred_text, assess_fit


class _FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]


class _FakePdfPage:
    def __init__(self, text: str):
        self.text = text

    def extract_text(self) -> str:
        return self.text


class _FakePdfReader:
    def __init__(self, _stream):
        self.pages = [_FakePdfPage("�� ��")]


class KoreanSupportTests(unittest.TestCase):
    @staticmethod
    def korean_candidate():
        return _profile_from_lines(
            [
                "성균관대학교 글로벌경영학과 재학 (2027년 2월 졸업예정)",
                "영어 OPIc IH, 한국어 원어민",
                "핵심역량: 전략기획, 시장조사, 데이터 분석, 유관부서 협업",
                "엑셀, 파워포인트, 파이썬, 생성형 AI",
                "시장 분석 프로젝트를 주도하고 보고서 작성",
            ],
            "korean_candidate.docx",
        )

    def test_korean_cv_extracts_evidence_languages_tools_and_education(self):
        candidate = self.korean_candidate()

        self.assertTrue({"strategy", "research", "data_analysis", "stakeholder"} <= candidate.evidence_tags)
        self.assertTrue({"korean", "english"} <= candidate.languages)
        self.assertTrue({"excel", "powerpoint", "python", "ai_tools"} <= candidate.tools)
        self.assertIsNotNone(candidate.graduation)
        self.assertTrue(candidate.education)

    def test_decorated_korean_sections_are_focused_and_split(self):
        text = (
            "■ 주요업무\n시장조사 및 전략기획\n"
            "[자격요건]\n경영학 전공 및 영어 능통자\n"
            "▶ 우대사항\n중국어 우대, Excel 활용 우대\n"
            "전형절차\n서류전형"
        )

        focused = focus_job_content(text)
        core, preferred = _split_preferred_text(focused)
        self.assertNotIn("전형절차", focused)
        self.assertIn("경영학", core)
        self.assertNotIn("중국어", core)
        self.assertIn("중국어", preferred)

    def test_korean_job_scores_against_korean_cv(self):
        result = assess_fit(
            self.korean_candidate(),
            JobPosting(
                title="글로벌 사업전략 인턴",
                company="Example",
                url="",
                text=(
                    "■ 담당업무\n시장조사와 전략기획, 유관부서 협업\n"
                    "[자격요건]\n경영학 또는 관련 전공, 영어 능통자, 재학생\n"
                    "▶ 우대사항\n중국어 우대, Excel과 Python 활용 우대"
                ),
            ),
        )

        self.assertGreaterEqual(result.score, 70)
        self.assertTrue(result.strengths)
        self.assertEqual(result.eligibility, "Pass")
        self.assertNotIn("Required language missing: Chinese", result.blockers)
        self.assertGreater(result.breakdown["Preferred alignment"], 0)

    def test_korean_required_and_preferred_language_are_different(self):
        candidate = self.korean_candidate()
        preferred = assess_fit(
            candidate,
            JobPosting(
                title="사업기획 인턴",
                company="Example",
                url="",
                text="지원자격\n경영학 전공\n우대사항\n중국어 우대",
            ),
        )
        required = assess_fit(
            candidate,
            JobPosting(
                title="중국사업 인턴",
                company="Example",
                url="",
                text="지원자격\n경영학 전공, 중국어 필수",
            ),
        )

        self.assertEqual(preferred.blockers, [])
        self.assertIn("Required language missing: Chinese", required.blockers)
        self.assertNotIn("business_degree", required.gaps)

    def test_mixed_korean_and_english_job_terms_are_detected(self):
        result = assess_fit(
            self.korean_candidate(),
            JobPosting(
                title="데이터 분석 인턴",
                company="Example",
                url="",
                text="담당업무\n시장 데이터 분석 및 dashboard 작성\n자격요건\nExcel, Python, 영어 가능자",
            ),
        )

        self.assertIn("data_analysis", result.strengths)
        self.assertNotIn("excel", result.gaps)
        self.assertNotIn("python", result.gaps)
        self.assertEqual(result.eligibility, "Pass")

    def test_cp949_job_page_is_decoded(self):
        html = (
            "<html><head><meta charset='euc-kr'><title>국문 전략 인턴</title></head>"
            "<body><h2>담당업무</h2><p>시장조사 및 전략기획을 수행합니다.</p></body></html>"
        ).encode("cp949")

        with patch("core.job_parser._public_ip_addresses", return_value=("93.184.216.34",)):
            with patch("core.job_parser._open_url", return_value=_FakeResponse(html)):
                posting = fetch_job_posting("https://example.com/ko/job")

        self.assertEqual(posting.source_status, "ok")
        self.assertIn("국문 전략 인턴", posting.title)
        self.assertIn("시장조사", posting.text)

    def test_pdfminer_fallback_recovers_korean_text(self):
        korean_text = "성균관대학교 글로벌경영학과 재학\n전략기획 및 시장조사 경험"
        with patch("core.cv_parser.PdfReader", _FakePdfReader), patch(
            "core.cv_parser._extract_pdfminer_text", return_value=korean_text
        ):
            lines = extract_pdf_bytes(b"not-a-real-pdf")

        self.assertEqual(lines, korean_text.splitlines())

    def test_ocr_fallback_runs_after_text_extractors_fail(self):
        korean_text = "국문 이미지 이력서\n전략기획 및 시장조사 경험"
        with patch("core.cv_parser.PdfReader", _FakePdfReader), patch(
            "core.cv_parser._extract_pdfminer_text", return_value=""
        ), patch("core.cv_parser._extract_pdf_with_ocr", return_value=korean_text) as ocr:
            lines = extract_pdf_bytes(b"not-a-real-pdf")

        ocr.assert_called_once()
        self.assertEqual(lines, korean_text.splitlines())


if __name__ == "__main__":
    unittest.main()
