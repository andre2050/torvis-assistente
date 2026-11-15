import hashlib, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class UpdateTests(unittest.TestCase):
 def test_verified_update_can_be_staged(self):
  with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as state:
   d=Path(td); f=d/'payload.bin'; f.write_bytes(b'assistente_inteligente-update')
   sha=hashlib.sha256(f.read_bytes()).hexdigest()
   (d/'update-manifest.json').write_text(json.dumps({'version':'1.0.1','files':{'payload.bin':sha}}))
   env=os.environ.copy(); env['ASSISTENTE_INTELIGENTE_STATE_DIR']=state
   code=f"from core.update_manager import stage_update; print(stage_update(r'{d}'))"
   r=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
 def test_bad_hash_is_rejected(self):
  with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as state:
   d=Path(td); (d/'x').write_text('x'); (d/'update-manifest.json').write_text(json.dumps({'version':'1','files':{'x':'bad'}}))
   env=os.environ.copy(); env['ASSISTENTE_INTELIGENTE_STATE_DIR']=state
   code=f"from core.update_manager import verify_package; verify_package(r'{d}')"
   r=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0)
if __name__=='__main__': unittest.main()
