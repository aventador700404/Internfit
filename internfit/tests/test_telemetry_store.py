import json
import os
import unittest
from unittest.mock import MagicMock, patch

from core.telemetry_store import build_storage_row, persist_analysis_event


class TelemetryStoreTests(unittest.TestCase):
    def test_storage_row_allowlist_excludes_source_content(self):
        row = build_storage_row({
            "event": "analysis_completed",
            "analysis_id": "abc123",
            "timestamp": "2026-09-05T00:00:00+00:00",
            "score": 61,
            "candidate_languages": ["english"],
            "raw_cv_text": "private CV content",
            "job_text": "private job content",
            "filename": "secret.pdf",
            "full_url": "https://example.com/private?id=secret",
        })

        self.assertIsNotNone(row)
        self.assertNotIn("raw_cv_text", row["payload"])
        self.assertNotIn("job_text", row["payload"])
        self.assertNotIn("filename", row["payload"])
        self.assertNotIn("full_url", row["payload"])
        self.assertEqual(row["payload"]["score"], 61)

    def test_disabled_without_server_credentials(self):
        with patch.dict(os.environ, {}, clear=True), patch("core.telemetry_store.urlopen") as urlopen:
            self.assertFalse(persist_analysis_event({
                "event": "analysis_completed",
                "analysis_id": "abc123",
            }))
            urlopen.assert_not_called()

    def test_posts_one_json_row_when_configured(self):
        response = MagicMock()
        response.__enter__.return_value = response
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://example.supabase.co/",
            "SUPABASE_SERVICE_ROLE_KEY": "server-only-key",
        }, clear=True), patch("core.telemetry_store.urlopen", return_value=response) as urlopen:
            self.assertTrue(persist_analysis_event({
                "event": "analysis_completed",
                "analysis_id": "abc123",
                "timestamp": "2026-09-05T00:00:00+00:00",
                "score": 61,
                "job_domain": "jobs.example.com",
            }))

        request = urlopen.call_args.args[0]
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://example.supabase.co/rest/v1/analysis_events")
        self.assertEqual(sent["analysis_id"], "abc123")
        self.assertEqual(sent["payload"]["score"], 61)
        self.assertNotIn("server-only-key", request.full_url)


if __name__ == "__main__":
    unittest.main()
