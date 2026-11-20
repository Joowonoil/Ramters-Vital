import subprocess
import unittest
from unittest.mock import patch

from codexvitals_windows import gemini_usage as gemini
from codexvitals_windows.app_settings import AppSettings


def report(*groups):
    return {"status": "SUCCESS", "command": {"name": "usage", "data": {"groups": list(groups)}}}


def bucket(id, window, fraction, **rest):
    return dict(bucketId=id, window=window, remainingFraction=fraction, **rest)


class GeminiUsageTests(unittest.TestCase):
    def test_weekly_only_zero_is_not_absence(self):
        main, = gemini.parse_report(report({"buckets": [bucket("gemini-weekly", "weekly", 0)]}))
        self.assertEqual([(w.period, w.remaining, w.resets_at) for w in main.windows],
                         [("1w", 0, None)])

    def test_shared_and_independent(self):
        main, argon, carbon = gemini.parse_report(report(
            {"description": "Models within this group: Gemini 4 Hydrogen, Gemini 4 Carbon",
             "buckets": [bucket("gemini-5h", "5h", .2)]},
            {"buckets": [bucket("gemini-argon-weekly", "1w", .32, resetTime="2026-01-02T12:30:00Z"),
                         bucket("3p-weekly", "1w", .99)]}))
        self.assertEqual(main.windows[0].remaining, 20)
        self.assertEqual((argon.label, argon.windows[0].remaining), ("Argon", 32))
        self.assertEqual(argon.windows[0].resets_at.hour, 12)
        self.assertEqual((carbon.label, carbon.shared, carbon.windows), ("Carbon", True, ()))

    def test_no_guessed_windows_or_raw_errors(self):
        for bad in [None, {}, {"status": "ERROR", "message": "private test value"},
                    report({"buckets": [bucket("gemini-weekly", "5h", .9)]}),
                    report({"buckets": [bucket("gemini-5h", "5h", True)]}),
                    report({"buckets": [bucket("gemini-weekly", "1w", 1, disabled=True)]})]:
            with self.subTest(bad=bad), self.assertRaisesRegex(gemini.UsageUnavailable, "^Gemini did not return"):
                gemini.parse_report(bad)

    def test_no_auto_login_on_failed_preflight(self):
        with patch.dict("os.environ", {"LOCALAPPDATA": str(gemini.Path.cwd())}), \
             patch.object(gemini.Path, "is_file", return_value=True), \
             patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as run:
            with self.assertRaisesRegex(gemini.UsageUnavailable, "sign-in"):
                gemini.fetch_usage()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][1:], ["models"])

    def test_legacy_installation_does_not_opt_in(self):
        self.assertFalse(AppSettings.from_dict({}).track_gemini)
        self.assertFalse(AppSettings.from_dict({"trackGemini": "yes"}).track_gemini)
        self.assertTrue(AppSettings.from_dict(AppSettings(track_gemini=True).to_dict()).track_gemini)
