import unittest
from unittest.mock import patch
from urllib.request import Request

from core.job_parser import UnsafeUrlError, _SafeRedirectHandler, fetch_job_posting


class _FakeResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def read(self, limit: int = -1) -> bytes:
        return self._body if limit < 0 else self._body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class JobParserTests(unittest.TestCase):
    def fetch_html(self, html: str):
        # Keep parser tests offline and independent of the machine's DNS.
        with patch("core.job_parser._public_ip_addresses", return_value=("93.184.216.34",)):
            with patch("core.job_parser._open_url", return_value=_FakeResponse(html)):
                return fetch_job_posting("https://example.com/jobs/1")

    def test_extracts_title_and_visible_job_text(self):
        posting = self.fetch_html("""
        <html><head><title>Example Strategy Intern</title></head>
        <body><h1>Strategy Intern</h1><p>Own planning and operations.</p><li>Excel required.</li></body></html>
        """)
        self.assertEqual(posting.source_status, "ok")
        self.assertIn("Example Strategy Intern", posting.title)
        self.assertIn("Own planning and operations.", posting.text)
        self.assertIn("Excel required.", posting.text)

    def test_ignores_script_text_that_can_inflate_scores(self):
        posting = self.fetch_html("""
        <html><head><title>Strategy Intern | Example Corp Careers</title>
        <script>technology finance japanese powerpoint operations strategy</script>
        <style>.strategy { color: green; }</style></head>
        <body><h1>Strategy Intern</h1><p>Support customer research.</p></body></html>
        """)
        self.assertEqual(posting.company, "Example Corp")
        self.assertIn("Support customer research.", posting.text)
        self.assertNotIn("japanese powerpoint", posting.text)

    def test_prefers_job_heading_over_generic_site_heading(self):
        posting = self.fetch_html("""
        <html><body><h1>Example Careers</h1>
        <section class="job_detail_header"><h3 class="title">Operations Intern</h3></section>
        </body></html>
        """)
        self.assertEqual(posting.title, "Operations Intern")

    def test_prefers_semantic_main_content_over_footer_keywords(self):
        posting = self.fetch_html("""
        <html><body>
        <main><h1>Finance Intern</h1><h2>Job responsibilities</h2>
        <p>Support variance analysis, reconciliation, and monthly reporting for the finance team.</p>
        <p>Use Excel to investigate discrepancies and document the result for stakeholders.</p>
        </main>
        <footer>Unrelated robotics software engineering jobs, Japanese and Chinese language roles.</footer>
        </body></html>
        """)
        self.assertIn("variance analysis", posting.text)
        self.assertNotIn("robotics software engineering", posting.text)

    def test_application_form_uses_full_text_when_main_is_only_form_controls(self):
        posting = self.fetch_html("""
        <html><head><title>Job Application for Intern, Chinese Speaking at Example</title></head>
        <body>
        <main><h1>Job Application for Intern, Chinese Speaking at Example</h1>
        <p>Requirements</p><form><label>First name</label><label>Last name</label>
        <label>Upload resume</label><label>Submit application</label></form></main>
        <section><h2>Qualifications</h2><p>Fluent Mandarin Chinese is required for this role.</p>
        <p>Support research and stakeholder coordination.</p></section>
        </body></html>
        """)
        self.assertIn("Fluent Mandarin Chinese", posting.text)

    def test_focuses_role_sections_and_drops_company_boilerplate(self):
        posting = self.fetch_html("""
        <html><body>
        <p>Qualcomm Overview</p><p>Global technology company with unrelated robotics jobs.</p>
        <main><h2>Role Overview</h2><p>Build and maintain an MCP server for this team.</p>
        <h2>Minimum Qualification</h2><p>Currently enrolled in a MS or PhD program in computer science.</p>
        <h2>About Qualcomm</h2><p>Company marketing and other opportunities.</p>
        </main>
        </body></html>
        """)
        self.assertIn("MCP server", posting.text)
        self.assertIn("MS or PhD", posting.text)
        self.assertNotIn("unrelated robotics", posting.text)
        self.assertNotIn("Company marketing", posting.text)

    def test_uses_jobposting_jsonld_for_client_rendered_pages(self):
        posting = self.fetch_html("""
        <html><head>
        <script type="application/ld+json">
        {"@type":"JobPosting","title":"AI Integration Intern","description":"Company Overview\\nUnrelated marketing.\\nRole Overview\\nBuild an MCP server.\\nMinimum Qualification:\\nCurrently enrolled in a MS or PhD degree program in computer science.","hiringOrganization":{"@type":"Organization","name":"Example"}}
        </script>
        </head><body><div id="app"></div></body></html>
        """)
        self.assertEqual(posting.title, "AI Integration Intern")
        self.assertEqual(posting.company, "Example")
        self.assertIn("Build an MCP server", posting.text)
        self.assertIn("Minimum Qualification", posting.text)
        self.assertNotIn("Unrelated marketing", posting.text)

    def test_rejects_empty_extraction_before_scoring(self):
        posting = self.fetch_html("""
        <html><head><title>Example Careers</title></head>
        <body><div id="app"></div></body></html>
        """)
        self.assertEqual(posting.source_status, "content_unusable: empty_text")
        self.assertEqual(posting.text, "")

    def test_rejects_blocked_page_shell(self):
        posting = self.fetch_html("""
        <html><head><title>Strategy Intern</title></head>
        <body><p>Enable JavaScript to continue. Checking your browser...</p></body></html>
        """)
        self.assertEqual(posting.source_status, "content_unusable: blocked_page")
        self.assertEqual(posting.text, "")

    def test_rejects_long_company_page_without_job_signals(self):
        generic_copy = "Company information and global news for visitors. " * 8
        posting = self.fetch_html(f"""
        <html><head><title>Example Careers</title></head>
        <body><p>{generic_copy}</p></body></html>
        """)
        self.assertEqual(posting.source_status, "content_unusable: no_job_signals")
        self.assertEqual(posting.text, "")

    def test_accepts_short_but_structured_job_posting(self):
        posting = self.fetch_html("""
        <html><head><title>Strategy Intern</title></head>
        <body><h2>Responsibilities</h2><p>Support research.</p>
        <h2>Requirements</h2><p>Excel required.</p></body></html>
        """)
        self.assertEqual(posting.source_status, "ok")
        self.assertIn("Support research", posting.text)

    def test_rejects_non_http_urls_before_opening(self):
        with patch("core.job_parser._open_url") as open_url:
            posting = fetch_job_posting("file:///etc/hostname")
        self.assertEqual(posting.source_status, "fetch_failed: UnsafeUrlError")
        open_url.assert_not_called()

    def test_rejects_private_and_loopback_addresses(self):
        unsafe_urls = (
            "http://127.0.0.1/job",
            "http://10.0.0.1/job",
            "http://192.168.1.1/job",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/job",
        )
        for url in unsafe_urls:
            with self.subTest(url=url):
                posting = fetch_job_posting(url)
                self.assertEqual(posting.source_status, "fetch_failed: UnsafeUrlError")

    def test_rejects_credentials_and_nonstandard_ports(self):
        for url in (
            "https://user:password@example.com/job",
            "https://example.com:8080/job",
        ):
            with self.subTest(url=url):
                with patch("core.job_parser._open_url") as open_url:
                    posting = fetch_job_posting(url)
                self.assertEqual(posting.source_status, "fetch_failed: UnsafeUrlError")
                open_url.assert_not_called()

    def test_redirect_handler_rejects_private_target(self):
        handler = _SafeRedirectHandler()
        with self.assertRaises(UnsafeUrlError):
            handler.redirect_request(
                Request("https://example.com/jobs/1"),
                None,
                302,
                "Found",
                {},
                "http://127.0.0.1/admin",
            )


if __name__ == "__main__":
    unittest.main()
