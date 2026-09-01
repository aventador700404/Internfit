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
