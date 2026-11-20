import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from codexvitals_windows import claude_observer as observer


class ClaudeTests(unittest.TestCase):
    def test_settings_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / "settings.json"
            config.write_text('{"theme":"dark"}')
            observer.configure(True, config, root)
            self.assertEqual(json.loads(config.read_text())["statusLine"], observer.ENTRY)
            observer.configure(False, config, root)
            self.assertEqual(json.loads(config.read_text()), {"theme": "dark"})
            config.write_text('{"statusLine":{"command":"existing"}}')
            with self.assertRaises(ValueError):
                observer.configure(True, config, root)
            self.assertEqual(json.loads(config.read_text())["statusLine"]["command"], "existing")

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell")
    def test_real_statusline_updates_without_copying_input(self):
        source = Path(__file__).resolve().parents[1] / "tools" / "ClaudeStatus.ps1"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            reset = int(time.time()) + 2000
            for used in (30, 76):
                payload = {"transcript_path": "do-not-persist", "rate_limits": {
                    "seven_day": {"resets_at": reset, "used_percentage": used}}}
                subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(source),
                                "-OutputDirectory", d], input=json.dumps(payload), text=True, check=True,
                               capture_output=True, timeout=10)
                path = root / "claude-usage.json"
                self.assertNotIn("do-not-persist", path.read_text())
                self.assertEqual(observer.latest(path)[1], (("1w", 100 - used, reset),))
                self.assertEqual(observer.latest(path, reset + 1)[1], ())
