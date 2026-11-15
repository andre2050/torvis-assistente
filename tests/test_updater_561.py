import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_default_update_source_is_official_github_repo():
    from core.update_manager import DEFAULT_UPDATE_MANIFEST_URL

    assert DEFAULT_UPDATE_MANIFEST_URL.startswith("https://raw.githubusercontent.com/")
    assert "andre2050/torvis-assistente" in DEFAULT_UPDATE_MANIFEST_URL
    assert DEFAULT_UPDATE_MANIFEST_URL.endswith("/update.json")


def test_version_comparison_handles_numeric_releases():
    from core.update_manager import is_newer_version

    assert is_newer_version("5.6.2", "5.6.1")
    assert is_newer_version("5.7.0", "5.6.99")
    assert not is_newer_version("5.6.1", "5.6.1")
    assert not is_newer_version("5.5.9", "5.6.1")


def _make_remote_update(base: Path, version: str = "9.9.9"):
    package_root = base / "package" / "T.O.R.V.I.S 2026"
    package_root.mkdir(parents=True)
    payload = package_root / "payload.txt"
    payload.write_text("torvis-update-payload", encoding="utf-8")
    payload_sha = hashlib.sha256(payload.read_bytes()).hexdigest()
    (package_root / "update-manifest.json").write_text(
        json.dumps({"version": version, "files": {"payload.txt": payload_sha}}),
        encoding="utf-8",
    )

    archive = base / f"TORVIS-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in package_root.rglob("*"):
            if item.is_file():
                zf.write(item, Path("T.O.R.V.I.S 2026") / item.relative_to(package_root))
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    remote = base / "update.json"
    remote.write_text(
        json.dumps(
            {
                "version": version,
                "channel": "stable",
                "package_url": archive.as_uri(),
                "sha256": archive_sha,
                "release_notes": "Teste local do atualizador.",
            }
        ),
        encoding="utf-8",
    )
    return remote, archive


def test_remote_manifest_can_be_validated_without_network():
    from core.update_manager import fetch_remote_manifest

    with tempfile.TemporaryDirectory() as td:
        remote, archive = _make_remote_update(Path(td))
        manifest = fetch_remote_manifest(remote.as_uri())
        assert manifest["version"] == "9.9.9"
        assert manifest["package_url"] == archive.as_uri()
        assert len(manifest["sha256"]) == 64


def test_prepare_remote_update_end_to_end_in_isolated_state_dir():
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as state:
        remote, _archive = _make_remote_update(Path(td))
        env = os.environ.copy()
        env["ASSISTENTE_INTELIGENTE_STATE_DIR"] = state
        code = (
            "import json; "
            "from core.update_manager import prepare_remote_update, read_pending_update; "
            f"r=prepare_remote_update(current_version='5.6.1', manifest_url={remote.as_uri()!r}); "
            "p=read_pending_update(); "
            "print(json.dumps({'prepared':r['prepared'],'remote':r['remote_version'],'pending':p['version'],'backup':bool(p.get('backup_path'))}))"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout.strip().splitlines()[-1])
        assert data == {
            "prepared": True,
            "remote": "9.9.9",
            "pending": "9.9.9",
            "backup": True,
        }


def test_bad_remote_zip_hash_is_rejected_before_extracting():
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as state:
        remote, _archive = _make_remote_update(Path(td))
        data = json.loads(remote.read_text(encoding="utf-8"))
        data["sha256"] = "0" * 64
        remote.write_text(json.dumps(data), encoding="utf-8")
        env = os.environ.copy()
        env["ASSISTENTE_INTELIGENTE_STATE_DIR"] = state
        code = (
            "from core.update_manager import prepare_remote_update; "
            f"prepare_remote_update(current_version='5.6.1', manifest_url={remote.as_uri()!r})"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0
        assert "SHA-256" in r.stderr


def test_internal_manifest_rejects_unlisted_files():
    from core.update_manager import verify_package

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = root / "good.txt"
        good.write_text("ok", encoding="utf-8")
        sha = hashlib.sha256(good.read_bytes()).hexdigest()
        (root / "update-manifest.json").write_text(
            json.dumps({"version": "9.9.9", "files": {"good.txt": sha}}),
            encoding="utf-8",
        )
        (root / "extra.py").write_text("print('unexpected')", encoding="utf-8")
        try:
            verify_package(root)
        except ValueError as exc:
            assert "unlisted update file" in str(exc)
        else:
            raise AssertionError("unlisted file should have been rejected")
