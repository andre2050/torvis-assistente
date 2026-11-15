"""Regressões essenciais da 6.0.0 RC1: pasta e Maps."""
from pathlib import Path
from unittest.mock import patch
import actions.file_controller as fc
from actions.google_maps import google_maps


def test_folder_verified_and_full_path(tmp_path):
    with patch.object(fc, "_SAFE_ROOTS", [tmp_path]):
        result = fc.create_folder(str(tmp_path), "minha-pasta")
        assert (tmp_path / "minha-pasta").is_dir()
        assert "criada e verificada" in result.lower()
        assert str(tmp_path / "minha-pasta") in result
        again = fc.create_folder(str(tmp_path), "minha-pasta")
        assert "já existia" in again


def test_folder_does_not_confirm_when_file_exists(tmp_path):
    (tmp_path / "ocupa").write_text("não é pasta")
    with patch.object(fc, "_SAFE_ROOTS", [tmp_path]):
        result = fc.create_folder(str(tmp_path), "ocupa")
    assert "não é uma pasta" in result
    assert "criada" not in result.lower()


def test_folder_rejects_outside_allowed_root(tmp_path):
    with patch.object(fc, "_SAFE_ROOTS", [tmp_path / "permitido"]):
        result = fc.create_folder(str(tmp_path / "negado"))
    assert "Access denied" in result
    assert not (tmp_path / "negado").exists()


def test_google_maps_query_escaped_and_opened():
    with patch("actions.google_maps.webbrowser.open", return_value=True) as opener:
        result = google_maps({"address": "Av. Paulista, São Paulo", "mode": "search"})
    assert "google.com/maps" in result
    assert "%C3%A3" in opener.call_args.args[0]
    assert "Confirme o endereço" in result


def test_google_maps_open_failure_not_success():
    with patch("actions.google_maps.webbrowser.open", return_value=False):
        result = google_maps({"address": "Bauru"})
    assert "Não foi possível confirmar" in result


def test_release_icon_and_build_contract():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "packaging/assistente_inteligente.spec").read_text(encoding="utf-8")
    inno = (root / "packaging/Assistente-Inteligente.iss").read_text(encoding="utf-8")
    assert 'name="TORVIS"' in spec
    assert 'MyAppExeName "TORVIS.exe"' in inno
    assert (root / "config/torvis_ultra.ico").is_file()
    assert (root / "config/torvis_ultra.png").is_file()
    assert (root / "VERSAO.txt").read_text().strip() == "6.0.0"
