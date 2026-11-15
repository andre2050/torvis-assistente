import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_state_override_is_respected():
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ, ASSISTENTE_INTELIGENTE_STATE_DIR=td, PYTHONPATH=str(ROOT))
        out = subprocess.check_output([sys.executable, '-c', 'from core.paths import STATE_DIR; print(STATE_DIR)'], env=env, text=True).strip()
        assert Path(out) == Path(td).resolve()
