# PyInstaller spec for T.O.R.V.I.S 2026 Windows builds.
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
for pkg in ("google.genai", "actions", "providers", "plugins"):
    hiddenimports += collect_submodules(pkg)

datas = []
for src, dst in (
    ("core/face_model.obj", "core"),
    ("core/prompt.txt", "core"),
    ("agents", "agents"),
    ("dashboard/static", "dashboard/static"),
    ("config/torvis_ultra.ico", "config"),
    ("config/torvis_ultra.png", "config"),
):
    if Path(src).exists():
        datas.append((src, dst))

a = Analysis(["main.py"], pathex=["."], binaries=[], datas=datas, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="TORVIS", console=False, icon="config/torvis_ultra.ico")
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="TORVIS")
