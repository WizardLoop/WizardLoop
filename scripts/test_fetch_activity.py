from datetime import datetime, timezone
import unittest

from fetch_activity import collect_events, event_record


def event(kind="PullRequestEvent", **extra):
    result = {
        "id": "123", "type": kind, "public": True,
        "actor": {"login": "WizardLoop"}, "repo": {"name": "WizardLoop/example"},
        "created_at": "2026-10-23T10:00:00Z",
        # Current GitHub responses can omit pull_request.user and commits.
        "payload": {"action": "opened", "number": 8, "pull_request": {}},
    }
    result.update(extra)
    return result


class ActivityTests(unittest.TestCase):
    def test_reduced_pull_request_payload_is_supported(self):
        record = event_record(event())
        self.assertEqual(record["text"], "Opened pull request #8 in WizardLoop/example")
        self.assertEqual(record["url"], "https://github.com/WizardLoop/example/pull/8")

    def test_push_without_commit_array_is_supported(self):
        record = event_record(event("PushEvent", payload={"ref": "refs/heads/main"}))
        self.assertEqual(record["text"], "Pushed updates to WizardLoop/example")

    def test_private_foreign_bot_and_profile_events_are_excluded(self):
        for change in (
            {"public": False},
            {"actor": {"login": "SomeoneElse"}},
            {"actor": {"login": "github-actions[bot]"}},
            {"repo": {"name": "WizardLoop/WizardLoop"}},
        ):
            self.assertIsNone(event_record(event(**change)))

    def test_failed_fetch_is_not_silently_converted_into_empty_activity(self):
        def fail(page):
            raise RuntimeError("upstream unavailable")
        with self.assertRaises(RuntimeError):
            collect_events(fail, datetime(2026, 10, 24, tzinfo=timezone.utc))

    def test_deduplicates_and_discards_old_events(self):
        now = datetime(2026, 10, 24, tzinfo=timezone.utc)
        records = collect_events(
            lambda page: [event(), event(), event(id="older", created_at="2025-10-23T10:00:00Z")],
            now,
        )
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
