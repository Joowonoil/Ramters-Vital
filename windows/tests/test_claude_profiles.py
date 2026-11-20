import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from codexvitals_windows import claude_profiles as cp


class ProfileTests(unittest.TestCase):
    def test_profiles_have_independent_statuslines_and_no_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            profiles = cp.Profiles(Path(d) / "claude-profiles")
            a, b = (profiles.add(n) for n in ("Work", "Personal"))
            self.assertNotEqual(a, b)
            for p, other in [(a, b), (b, a)]:
                line = json.loads((p / "settings.json").read_text())["statusLine"]["command"]
                self.assertIn(p.name, line)
                self.assertNotIn(other.name, line)
                self.assertEqual({f.name for f in p.iterdir()}, {"label.txt", "settings.json"})
            self.assertEqual(cp.Profiles(profiles.root).items(), [("Personal", b), ("Work", a)])
            with self.assertRaises(ValueError):
                profiles.add("work")

    def test_switch_preserves_existing_environment_and_refuses_external_change(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            profiles = cp.Profiles(root / "claude-profiles")
            a, b = (profiles.add(n) for n in ("A", "B"))
            previous = [str(root / "preexisting"), 2]
            registry = {"current": previous}
            with patch.object(cp, "_user_setting", side_effect=lambda: registry["current"]), \
                 patch.object(cp, "_set_user_setting", side_effect=lambda v: registry.update(current=v)):
                profiles.activate(a)
                self.assertEqual(profiles.active_path(), a)
                profiles.activate(b)
                self.assertEqual(profiles.active_path(), b)
                registry["current"] = [str(root / "external"), 1]
                with self.assertRaises(ValueError):
                    profiles.activate(None)
                registry["current"] = [str(b), 1]
                profiles.activate(None)
                self.assertEqual(registry["current"], previous)
                self.assertFalse(profiles.baseline.exists())

    @unittest.skipUnless(os.name == "nt", "Windows process creation")
    def test_generated_status_lines_do_not_mix_samples(self):
        with tempfile.TemporaryDirectory() as d:
            fake_local = Path(d)
            profiles = cp.Profiles(fake_local / "RamterStudio" / "Vital" / "claude-profiles")
            a, b = (profiles.add(n) for n in ("A", "B"))
            reset = int(time.time()) + 7200
            for p, used in ((a, 25), (b, 80), (a, 50)):
                cmd = json.loads((p / "settings.json").read_text())["statusLine"]["command"]
                cmd = cmd.replace("[Environment]::GetFolderPath('LocalApplicationData')",
                                  "'" + str(fake_local).replace("'", "''") + "'")
                raw = json.dumps({"rate_limits": {"five_hour": {"used_percentage": used, "resets_at": reset}}})
                subprocess.run(cmd, input=raw, capture_output=True, text=True, check=True, timeout=10)
            for p, remaining in ((a, 50), (b, 20)):
                self.assertEqual(cp.claude_observer.latest(p / "claude-usage.json")[1],
                                 (("5h", remaining, reset),))

    @unittest.skipUnless(os.name == "nt", "Windows process creation")
    def test_launch_uses_child_environment_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            profiles = cp.Profiles(root / "claude-profiles")
            target = profiles.add("Test")
            (root / "claude.exe").touch()
            with patch.dict(os.environ, {"PATH": d, "CLAUDE_CONFIG_DIR": "unchanged"}), \
                 patch.object(cp, "_user_setting", return_value=None), \
                 patch.object(cp.subprocess, "Popen") as popen:
                profiles.launch(target)
                self.assertEqual(popen.call_args.kwargs["env"]["CLAUDE_CONFIG_DIR"], str(target))
                self.assertEqual(os.environ["CLAUDE_CONFIG_DIR"], "unchanged")
