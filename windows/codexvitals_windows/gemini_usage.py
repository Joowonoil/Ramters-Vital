"""Read the signed-in Antigravity CLI's own quota report, without handling OAuth."""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class UsageUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Window:
    period: str
    remaining: float
    resets_at: datetime | None


@dataclass(frozen=True)
class ModelQuota:
    label: str
    windows: tuple[Window, ...]
    shared: bool = False


def _reset(value):
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo is not None else None
        except ValueError:
            pass
    return None


def parse_report(data):
    unavailable = "Gemini did not return a usable quota report."
    if not isinstance(data, dict) or data.get("status") != "SUCCESS":
        raise UsageUnavailable(unavailable)
    command = data.get("command")
    if not isinstance(command, dict) or command.get("name") != "usage":
        raise UsageUnavailable(unavailable)
    payload = command.get("data")
    groups = payload.get("groups") if isinstance(payload, dict) else None
    if not isinstance(groups, list):
        raise UsageUnavailable(unavailable)

    labels = ("Gemini", "Argon", "Carbon", "Hydrogen")
    models = {f"gemini 4 {label.lower()}": label for label in labels[1:]}
    windows = {label: {} for label in labels}
    shared, scoped = set(), set()
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("buckets"), list):
            continue
        named = models.get(str(group.get("displayName", "")).lower())
        for bucket in group["buckets"]:
            if not isinstance(bucket, dict):
                continue
            key = bucket.get("id", bucket.get("bucketId"))
            if not isinstance(key, str) or key.startswith("3p-"):
                continue
            main = key in ("gemini-5h", "gemini-weekly")
            label = "Gemini" if main else next(
                (s for s in labels[1:] if key.startswith(f"gemini-{s.lower()}-")), named)
            if label is None:
                continue
            if not main:
                scoped.add(label)
            if bucket.get("disabled") is True:
                continue
            if main:
                if named:
                    shared.add(named)
                desc = group.get("description")
                prefix = "Models within this group:"
                if isinstance(desc, str) and desc.startswith(prefix):
                    shared.update(models.get(s.strip().lower()) for s in desc[len(prefix):].split(","))
            period = {"5h": "5h", "weekly": "1w", "1w": "1w"}.get(str(bucket.get("window")))
            fraction = bucket.get("remaining_fraction", bucket.get("remainingFraction"))
            if (not period or (key.endswith("-5h") and period != "5h")
                    or (key.endswith("-weekly") and period != "1w")
                    or type(fraction) not in (int, float) or not 0 <= fraction <= 1):
                continue
            reset = _reset(bucket.get("reset_time", bucket.get("resetTime")))
            windows[label].setdefault(period, Window(period, fraction * 100, reset))
    if not windows["Gemini"]:
        raise UsageUnavailable(unavailable)
    result = []
    for label in labels:
        if windows[label]:
            result.append(ModelQuota(label, tuple(windows[label][p] for p in ("5h", "1w") if p in windows[label])))
        elif label in shared and label not in scoped and label != "Hydrogen":
            result.append(ModelQuota(label, (), True))
    return tuple(result)


def _executable():
    default = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"
    candidates = [default, *(Path(entry) / "agy.exe" for entry in os.get_exec_path())]
    executable = next((p for p in candidates if p.is_absolute() and p.is_file()), None)
    if executable is None:
        raise UsageUnavailable("Install Antigravity CLI to see Gemini usage.")
    return executable


def open_cli():
    subprocess.Popen([str(_executable())], cwd=Path.home(), creationflags=subprocess.CREATE_NEW_CONSOLE)


def fetch_usage():
    executable = _executable()
    try:
        with tempfile.TemporaryDirectory() as cwd:
            opts = dict(cwd=cwd, stdin=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            # An unauthenticated --print can start browser login even with no stdin.
            check = subprocess.run([executable, "models"], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=10, **opts)
            if check.returncode:
                raise UsageUnavailable("Open agy and check your sign-in before refreshing Gemini.")
            proc = subprocess.run(
                [executable, "--print", "/usage", "--output-format", "json", "--print-timeout", "20s"],
                capture_output=True, timeout=25, **opts)
        if proc.returncode:
            raise UsageUnavailable("Check your sign-in and quota with agy /usage.")
        return parse_report(json.loads(proc.stdout))
    except subprocess.TimeoutExpired:
        raise UsageUnavailable("Gemini usage check timed out.") from None
    except (OSError, ValueError, UnicodeError):
        raise UsageUnavailable("Antigravity CLI could not provide its quota report.") from None
