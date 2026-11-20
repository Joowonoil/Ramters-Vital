"""Opt-in Claude Code status line. No credentials, transcripts or network access."""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from uuid import UUID

from .file_locations import localappdata_directory

COMMAND = ("powershell.exe -NoProfile -NonInteractive -Command "
           "\"& ([IO.Path]::Combine([Environment]::GetFolderPath('LocalApplicationData'),"
           "'RamterStudio','Vital','ClaudeStatus.ps1'))\"")
ENTRY = {"type": "command", "command": COMMAND}

class StatusLineInUse(ValueError):
    pass


def configure(enabled, config=None, directory=None, *, profile_id=None):
    config = config or Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"
    directory = directory or localappdata_directory() / "RamterStudio" / "Vital"
    entry = ENTRY
    sample_dir = directory
    if profile_id is not None:
        profile_id = str(UUID(profile_id))
        output = (" ([IO.Path]::Combine([Environment]::GetFolderPath('LocalApplicationData'),"
                  f"'RamterStudio','Vital','claude-profiles','{profile_id}'))")
        entry = dict(ENTRY, command=COMMAND[:-1] + " -OutputDirectory" + output + '"')
        sample_dir = directory / "claude-profiles" / profile_id
    previous = config.read_bytes() if config.exists() else None
    data = json.loads(previous.decode("utf-8-sig")) if previous is not None else {}
    if not isinstance(data, dict):
        raise ValueError("Claude Code settings are not a JSON object.")
    if enabled and "statusLine" in data and data["statusLine"] != entry:
        raise StatusLineInUse("Your existing Claude Code status line was left unchanged.")
    if enabled:
        source = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "tools" / "ClaudeStatus.ps1"
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, directory / "ClaudeStatus.ps1")
        data["statusLine"] = entry
    elif data.get("statusLine") == entry:
        del data["statusLine"]
    else:
        return
    config.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=config.parent, delete=False) as f:
        tmp = Path(f.name)
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if (config.read_bytes() if config.exists() else None) != previous:
            raise ValueError("Claude Code settings changed. Please try again.")
        tmp.replace(config)
    finally:
        tmp.unlink(missing_ok=True)
    if not enabled:
        (sample_dir / "claude-usage.json").unlink(missing_ok=True)


def latest(path=None, now=None):
    path = path or localappdata_directory() / "RamterStudio" / "Vital" / "claude-usage.json"
    now = time.time() if now is None else now
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        ts = data["observed"]
        if type(ts) is not int or not 0 <= now - ts <= 7 * 86400:
            return None, ()
        rows = []
        for key, label in (("five_hour", "5h"), ("seven_day", "1w")):
            w = data["windows"].get(key)
            if isinstance(w, dict) and type(w.get("remaining")) in (int, float) and 0 <= w["remaining"] <= 100:
                reset = w.get("reset")
                if type(reset) is int and now < reset <= ts + 8 * 86400:
                    rows.append((label, w["remaining"], reset))
        return ts, tuple(rows)
    except (ValueError, AttributeError, KeyError, TypeError, OSError):
        return None, ()
