import json
import unittest
from unittest.mock import patch

from core.telemetry import emit_analysis_event, new_analysis_id, safe_url_domain


class TelemetryTests(unittest.TestCase):
    def test_analysis_id_is_short_and_nonempty(self):
        analysis_id = new_analysis_id()
        self.assertEqual(len(analysis_id), 16)
        self.assertNotEqual(analysis_id, new_analysis_id())

    def test_domain_strips_path_and_query(self):
        self.assertEqual(
            safe_url_domain("https://jobs.example.com/path?token=secret"),
            "jobs.example.com",
        )

    def test_emits_json_event_with_derived_fields_only(self):
        with patch("builtins.print") as output:
            emit_analysis_event(
                "analysis_completed",
                "abc123",
                score=72,
                cv_size_bytes=1234,
                job_domain="jobs.example.com",
                candidate_tags=["research"],
            )

        record = json.loads(output.call_args.args[0])
        self.assertEqual(record["event"], "analysis_completed")
        self.assertEqual(record["analysis_id"], "abc123")
        self.assertEqual(record["score"], 72)
        self.assertNotIn("raw_text", record)
        self.assertNotIn("job_text", record)


if __name__ == "__main__":
    unittest.main()
