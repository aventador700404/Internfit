from pathlib import Path
from tempfile import NamedTemporaryFile
import unittest

from core.job_parser import fetch_job_posting


class JobParserTests(unittest.TestCase):
    def test_extracts_title_and_visible_job_text(self):
        html = """
        <html><head><title>Example Strategy Intern</title></head>
        <body><h1>Strategy Intern</h1><p>Own planning and operations.</p><li>Excel required.</li></body></html>
        """
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as file:
            file.write(html)
            path = Path(file.name)
        try:
            posting = fetch_job_posting(path.as_uri())
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(posting.source_status, "ok")
        self.assertIn("Example Strategy Intern", posting.title)
        self.assertIn("Own planning and operations.", posting.text)
        self.assertIn("Excel required.", posting.text)

    def test_ignores_script_text_that_can_inflate_scores(self):
        html = """
        <html><head><title>Strategy Intern | Example Corp Careers</title>
        <script>technology finance japanese powerpoint operations strategy</script>
        <style>.strategy { color: green; }</style></head>
        <body><h1>Strategy Intern</h1><p>Support customer research.</p></body></html>
        """
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as file:
            file.write(html)
            path = Path(file.name)
        try:
            posting = fetch_job_posting(path.as_uri())
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(posting.company, "Example Corp")
        self.assertIn("Support customer research.", posting.text)
        self.assertNotIn("japanese powerpoint", posting.text)

    def test_prefers_job_heading_over_generic_site_heading(self):
        html = """
        <html><body><h1>Example Careers</h1>
        <section class="job_detail_header"><h3 class="title">Operations Intern</h3></section>
        </body></html>
        """
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as file:
            file.write(html)
            path = Path(file.name)
        try:
            posting = fetch_job_posting(path.as_uri())
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(posting.title, "Operations Intern")

    def test_prefers_semantic_main_content_over_footer_keywords(self):
        html = """
        <html><body>
        <main><h1>Finance Intern</h1><h2>Job responsibilities</h2>
        <p>Support variance analysis, reconciliation, and monthly reporting for the finance team.</p>
        <p>Use Excel to investigate discrepancies and document the result for stakeholders.</p>
        </main>
        <footer>Unrelated robotics software engineering jobs, Japanese and Chinese language roles.</footer>
        </body></html>
        """
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as file:
            file.write(html)
            path = Path(file.name)
        try:
            posting = fetch_job_posting(path.as_uri())
        finally:
            path.unlink(missing_ok=True)
        self.assertIn("variance analysis", posting.text)
        self.assertNotIn("robotics software engineering", posting.text)

    def test_application_form_uses_full_text_when_main_is_only_form_controls(self):
        html = """
        <html><head><title>Job Application for Intern, Chinese Speaking at Example</title></head>
        <body>
        <main><h1>Job Application for Intern, Chinese Speaking at Example</h1>
        <p>Requirements</p><form><label>First name</label><label>Last name</label>
        <label>Upload resume</label><label>Submit application</label></form></main>
        <section><h2>Qualifications</h2><p>Fluent Mandarin Chinese is required for this role.</p>
        <p>Support research and stakeholder coordination.</p></section>
        </body></html>
        """
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as file:
            file.write(html)
            path = Path(file.name)
        try:
            posting = fetch_job_posting(path.as_uri())
        finally:
            path.unlink(missing_ok=True)
        self.assertIn("Fluent Mandarin Chinese", posting.text)

    def test_focuses_role_sections_and_drops_company_boilerplate(self):
        html = """
        <html><body>
        <p>Qualcomm Overview</p><p>Global technology company with unrelated robotics jobs.</p>
        <main><h2>Role Overview</h2><p>Build and maintain an MCP server for this team.</p>
        <h2>Minimum Qualification</h2><p>Currently enrolled in a MS or PhD program in computer science.</p>
        <h2>About Qualcomm</h2><p>Company marketing and other opportunities.</p>
        </main>
        </body></html>
        """
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as file:
            file.write(html)
            path = Path(file.name)
        try:
            posting = fetch_job_posting(path.as_uri())
        finally:
            path.unlink(missing_ok=True)
        self.assertIn("MCP server", posting.text)
        self.assertIn("MS or PhD", posting.text)
        self.assertNotIn("unrelated robotics", posting.text)
        self.assertNotIn("Company marketing", posting.text)

    def test_uses_jobposting_jsonld_for_client_rendered_pages(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type":"JobPosting","title":"AI Integration Intern","description":"Company Overview\\nUnrelated marketing.\\nRole Overview\\nBuild an MCP server.\\nMinimum Qualification:\\nCurrently enrolled in a MS or PhD degree program in computer science.","hiringOrganization":{"@type":"Organization","name":"Example"}}
        </script>
        </head><body><div id="app"></div></body></html>
        """
        with NamedTemporaryFile(mode="w", suffix=".html", delete=False) as file:
            file.write(html)
            path = Path(file.name)
        try:
            posting = fetch_job_posting(path.as_uri())
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(posting.title, "AI Integration Intern")
        self.assertEqual(posting.company, "Example")
        self.assertIn("Build an MCP server", posting.text)
        self.assertIn("Minimum Qualification", posting.text)
        self.assertNotIn("Unrelated marketing", posting.text)
