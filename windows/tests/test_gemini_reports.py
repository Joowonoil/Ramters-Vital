import datetime
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from codexvitals_windows import gemini_reports as gr


class GeminiReportsTests(unittest.TestCase):
    def test_linking_respects_existing_statusline_and_settings(self):
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / "settings.json"
            cache = Path(d) / "reports"
            config.write_text('{"statusLine":{"command":"custom"}}')
            with self.assertRaises(ValueError):
                gr.configure(True, cache, config)
            self.assertFalse(cache.exists())
            config.write_text('{"theme":"dark"}')
            gr.configure(True, cache, config)
            self.assertTrue(json.loads(config.read_text())["statusLine"]["stack_with_default"])
            gr.configure(False, cache, config)
            self.assertEqual(json.loads(config.read_text()), {"theme": "dark"})

    @unittest.skipUnless(os.name == "nt", "Windows status line")
    def test_account_attribution_a_b_a_and_forget(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "reports"
            conf = Path(d) / "settings.json"
            gr.configure(True, cache, conf)
            epoch = int(time.time()) + 3600
            reset = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()
            for mail, pct in [("a@example.test", .95), ("b@example.test", .3), ("a@example.test", .8)]:
                payload = {"product":"antigravity", "email":mail, "plan_tier":"Pro",
                           "conversation_title":"PRIVATE_TEST", "quota":{
                               "gemini-weekly":{"remaining_fraction":pct, "reset_time":reset},
                               "gemini-carbon-weekly":{"disabled":True,"remaining_fraction":1},
                               "3p-weekly":{"remaining_fraction":.5}}}
                subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-File",
                                str(cache / "GeminiStatus.ps1"), "-Directory", str(cache)],
                               text=True, input=json.dumps(payload), capture_output=True, check=True, timeout=10)
            samples = gr.accounts(cache)
            self.assertEqual([(s[0], s[3]) for s in samples], [
                ("a@example.test", [("Gemini","1w",80,epoch)]),
                ("b@example.test", [("Gemini","1w",30,epoch)])])
            self.assertTrue(all(not s[3] for s in gr.accounts(cache, epoch+1)))
            self.assertNotIn("PRIVATE_TEST", "".join(p.read_text() for p in cache.glob("*.json")))
            gr.configure(False, cache, conf)
            self.assertFalse(list(cache.glob("*.json")))
