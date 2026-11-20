"""Claude Code owns credentials. Vital only selects its configuration directory."""
import ctypes
import json
import os
import shutil
import subprocess
from pathlib import Path
from uuid import UUID, uuid4

from . import claude_observer
from .file_locations import localappdata_directory


class Profiles:
    def __init__(self, root=None):
        self.root = root or localappdata_directory() / "RamterStudio" / "Vital" / "claude-profiles"

    def items(self):
        result = []
        if self.root.is_dir():
            for path in self.root.iterdir():
                try:
                    if str(UUID(path.name)) == path.name:
                        name = (path / "label.txt").read_text(encoding="utf-8").strip()
                        if name:
                            result.append((name, path))
                except (ValueError, OSError):
                    continue
        return sorted(result, key=lambda item: (item[0].casefold(), item[1].name))

    def add(self, label):
        label = label.strip()
        if not label or len(label) > 80 or not label.isprintable():
            raise ValueError("Choose a profile name between 1 and 80 characters.")
        if label.casefold() in {"original", *(n.casefold() for n, _ in self.items())}:
            raise ValueError("This profile name is already in use.")
        path = self.root / str(uuid4())
        path.mkdir(parents=True)
        try:
            claude_observer.configure(True, path / "settings.json", self.root.parent,
                                     profile_id=path.name)
            (path / "label.txt").write_text(label, encoding="utf-8")
        except Exception:
            # This newly created directory has not yet been passed to Claude.
            shutil.rmtree(path)
            raise
        return path

    @property
    def baseline(self):
        return self.root / "original-environment.json"

    def original(self):
        if self.baseline.is_file():
            return json.loads(self.baseline.read_text(encoding="utf-8"))
        return _user_setting()

    def original_path(self):
        pair = self.original()
        return Path(os.path.expandvars(pair[0])) if pair else Path.home() / ".claude"

    def activate(self, path):
        managed = {p for _, p in self.items()}
        if path is not None and path not in managed:
            raise ValueError("This Claude profile is not registered.")
        original = self.original()
        current = _user_setting()
        if current != original and (not current or Path(current[0]) not in managed):
            raise ValueError("CLAUDE_CONFIG_DIR was changed outside Vital. No change was made.")
        if path is not None and not self.baseline.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            with self.baseline.open("x", encoding="utf-8") as f:
                json.dump(original, f)
        _set_user_setting([str(path), 1] if path is not None else original)
        if path is None:
            self.baseline.unlink(missing_ok=True)

    def active_path(self):
        current = _user_setting()
        return Path(os.path.expandvars(current[0])) if current else Path.home() / ".claude"

    def launch(self, path, *, sign_in=False):
        if path != self.original_path() and path not in {p for _, p in self.items()}:
            raise ValueError("Choose a registered Claude profile.")
        # Do not resolve a CLI from the working directory or pass labels to a shell.
        candidates = (Path(entry) / name for entry in os.get_exec_path() if os.path.isabs(entry)
                      for name in ("claude.exe", "claude.cmd"))
        binary = next((p for p in candidates if p.is_file()), None)
        if not binary:
            raise ValueError("Install Claude Code for Windows first.")
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(path))
        subprocess.Popen([str(binary), *(["auth", "login"] if sign_in else [])], env=env, cwd=Path.home(),
                         creationflags=subprocess.CREATE_NEW_CONSOLE)


def _user_setting():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, kind = winreg.QueryValueEx(key, "CLAUDE_CONFIG_DIR")
            if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                raise ValueError("Unsupported CLAUDE_CONFIG_DIR registry type.")
            return [value, kind]
    except FileNotFoundError:
        return None


def _set_user_setting(pair):
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        if pair is None:
            try:
                winreg.DeleteValue(key, "CLAUDE_CONFIG_DIR")
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, "CLAUDE_CONFIG_DIR", 0, pair[1], pair[0])
    # Already-open terminal processes retain their inherited environments.
    ctypes.windll.user32.SendMessageTimeoutW(0xffff, 0x001A, 0, ctypes.c_wchar_p("Environment"),
                                             2, 300, None)
