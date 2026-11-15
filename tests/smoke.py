"""Dependency-light smoke checks for CI/build machines."""
import compileall
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from core.paths import ensure_state_dirs, STATE_DIR

assert compileall.compile_dir(root, quiet=1)
ensure_state_dirs()
assert STATE_DIR.exists()
print('SMOKE OK')
