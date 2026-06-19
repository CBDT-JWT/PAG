import os
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"
RUNS_DIR = PUBLIC_DIR / "runs"
PRESETS_DIR = PUBLIC_DIR / "presets"
PRESET_ASSETS_DIR = PRESETS_DIR / "assets"
PRESETS_FILE = PRESETS_DIR / "theme-presets.local.json"
PRESETS_EXAMPLE_FILE = PRESETS_DIR / "theme-presets.example.json"
PRESETS_LEGACY_FILE = PRESETS_DIR / "theme-presets.json"
ASSETS_DIR = BASE_DIR / "assets"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
PORT = int(os.environ.get("PORT", "5001"))
MAX_PAPER_CHARS = 240000


def load_env():
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    try:
        content = subprocess.check_output(["/bin/cat", str(path)], text=True, timeout=2)
    except Exception:
        return
    for raw in content.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
