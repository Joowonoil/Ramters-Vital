"""Account-attributed samples emitted by agy. Never assign /usage to a guessed identity."""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

from .file_locations import localappdata_directory

ENTRY = {"type": "command", "stack_with_default": True, "command":
         'powershell.exe -NoLogo -NoProfile -NonInteractive -Command '
         '"& ([IO.Path]::Combine([Environment]::GetFolderPath(\'LocalApplicationData\'),'
         "'RamterStudio','Vital','Gemini','GeminiStatus.ps1'))\""}
KEY = re.compile(r"gemini-(?:(argon|carbon|hydrogen)-)?(5h|weekly)")


def folder():
    return localappdata_directory() / "RamterStudio" / "Vital" / "Gemini"


def linked():
    return (folder() / "enabled").is_file()


def configure(enable, directory=None, config=None):
    directory = directory or folder()
    config = config or Path.home() / ".gemini/antigravity-cli/settings.json"
    previous = config.read_bytes() if config.exists() else None
    data = json.loads(previous.decode("utf-8-sig")) if previous is not None else {}
    if not isinstance(data, dict):
        raise ValueError("Invalid agy settings; no changes made.")
    ours = data.get("statusLine") == ENTRY
    marker = directory / "enabled"
    if enable:
        if "statusLine" in data and not ours:
            raise ValueError("agy already has a custom status line; it has not been replaced.")
        directory.mkdir(parents=True, exist_ok=True)
        source = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "tools/GeminiStatus.ps1"
        shutil.copyfile(source, directory / "GeminiStatus.ps1")
        data["statusLine"] = ENTRY
    else:
        marker.unlink(missing_ok=True)
        if ours:
            del data["statusLine"]
    if enable or ours:
        config.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=config.parent, delete=False) as f:
            tmp = Path(f.name)
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if (config.read_bytes() if config.exists() else None) != previous:
                raise ValueError("agy settings changed; try again.")
            os.replace(tmp, config)
        finally:
            tmp.unlink(missing_ok=True)
    if enable:
        marker.touch()
    elif directory.is_dir():
        for path in directory.glob("*.json"):
            if re.fullmatch(r"[a-f0-9]{64}", path.stem):
                path.unlink(missing_ok=True)


def accounts(directory=None, now=None):
    directory = directory or folder()
    now = time.time() if now is None else now
    result = []
    if not (directory / "enabled").is_file():
        return result
    for path in directory.glob("*.json"):
        try:
            if path.stat().st_size > 32768:
                continue
            item = json.loads(path.read_bytes())
            mail, ts = item["email"], item["observed"]
            if not isinstance(mail, str) or hashlib.sha256(mail.encode()).hexdigest() != path.stem:
                continue
            if type(ts) is not int or not 0 < ts <= now + 60:
                continue
            readings = []
            for key, w in item["quotas"].items():
                m = KEY.fullmatch(key)
                if not m or not isinstance(w, dict):
                    continue
                fraction, reset = w.get("remaining"), w.get("reset")
                if type(fraction) not in (int, float) or not 0 <= fraction <= 1:
                    continue
                period = "1w" if m[2] == "weekly" else "5h"
                if reset is None:
                    if now - ts > (604800 if period == "1w" else 18000):
                        continue
                elif type(reset) is not int or not now < reset < 32503680000:
                    continue
                readings.append(((m[1] or "gemini").title(), period, fraction * 100, reset))
            result.append((mail, str(item.get("plan") or ""), ts, readings))
        except (ValueError, UnicodeError, KeyError, TypeError, AttributeError, OSError):
            continue
    return sorted(result, key=lambda r: r[0])
