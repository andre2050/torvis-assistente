import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class FoundationTests(unittest.TestCase):
    def test_assistente_inteligente_state_is_external_and_writable(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy(); env['ASSISTENTE_INTELIGENTE_STATE_DIR'] = td
            code = "from core.paths import STATE_DIR,APP_DIR,ensure_state_dirs; ensure_state_dirs(); print(STATE_DIR); assert STATE_DIR != APP_DIR"
            r = subprocess.run([sys.executable,'-c',code], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_config_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy(); env['ASSISTENTE_INTELIGENTE_STATE_DIR'] = td
            code = "from memory.config_manager import save_assistant_config,get_assistant_name; save_assistant_config('Assistente Inteligente','Andre Luiz Lima Menezes'); assert get_assistant_name()=='Assistente Inteligente'"
            r = subprocess.run([sys.executable,'-c',code], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_smoke_harness_default_mode(self):
        r = subprocess.run([sys.executable, str(ROOT/'core'/'_smoke_harness.py')], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('@@REPORT@@', r.stdout)

if __name__ == '__main__': unittest.main()
