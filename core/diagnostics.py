"""Small dependency/state health check usable before the GUI starts."""
from __future__ import annotations
import importlib.util
import json
import platform
import sys
from core.paths import STATE_DIR, CONFIG_FILE, MEMORY_FILE, ensure_state_dirs

REQUIRED = ("PyQt6", "numpy", "sounddevice", "httpx", "google.genai")


def run() -> dict:
    ensure_state_dirs()
    deps = {name: importlib.util.find_spec(name) is not None for name in REQUIRED}
    writable = True
    probe = STATE_DIR / ".write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError:
        writable = False
    return {
        "python": sys.version.split()[0], "platform": platform.platform(),
        "state_dir": str(STATE_DIR), "state_writable": writable,
        "config_present": CONFIG_FILE.exists(), "memory_present": MEMORY_FILE.exists(),
        "dependencies": deps, "ok": writable and all(deps.values()),
    }

if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
