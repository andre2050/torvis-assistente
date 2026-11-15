from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def _load_gemini():
    spec = importlib.util.spec_from_file_location("torvis_gemini_564", ROOT / "core" / "gemini.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_live_ladder_has_current_failover():
    g = _load_gemini()
    assert g.LIVE_MODELS[0] == "models/gemini-3.1-flash-live-preview"
    assert "models/gemini-3.8-live" in g.LIVE_MODELS


def test_1011_is_transient_live_transport_error():
    g = _load_gemini()
    assert g.is_live_transport_error("APIError: 1011 None. Internal error encountered.")
    assert g.is_live_transport_error("ConnectionClosedError: received 1011 internal error")
    assert not g.is_live_transport_error("API key not valid")


def test_main_flattens_exception_groups_and_recovers_1011():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "def _exception_text(" in src
    assert "def _is_live_1011(" in src
    assert "self._live_1011_streak >= 2" in src
    assert "self._resume_handle = None" in src
    assert "reconectando automaticamente" in src


def test_release_version_564():
    from core.version import VERSAO
    assert tuple(map(int, VERSAO.split("."))) >= (5, 6, 4)
