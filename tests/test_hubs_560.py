import ast
from pathlib import Path


def _renderer_source():
    return Path('gui/hubs_realistic.py').read_text(encoding='utf-8')


def test_realistic_hub_catalog_is_complete_without_requiring_qt_runtime():
    tree = ast.parse(_renderer_source())
    values = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'REALISTIC_HUBS':
                    values = ast.literal_eval(node.value)
    expected = {"hexagono", "prisma", "cubo", "iris", "engrenagem", "atomo", "mandala", "espectro", "vortice"}
    assert values is not None
    assert set(values) == expected


def test_all_10_user_hubs_are_preserved_in_config():
    from memory.config_manager import HUD_STYLES
    expected = {"reator", "hexagono", "prisma", "cubo", "iris", "engrenagem", "atomo", "mandala", "espectro", "vortice"}
    assert expected.issubset(set(HUD_STYLES))


def test_hud_uses_realistic_renderer_and_keeps_fallback():
    source = Path('gui/hud.py').read_text(encoding='utf-8')
    assert 'RealisticHubRenderer' in source
    assert 'self._hub_renderer.paint' in source
    assert 'elif estilo == "vortice"' in source


def test_renderer_has_one_painter_per_geometric_hub():
    source = _renderer_source()
    for style in ("hexagono", "prisma", "cubo", "iris", "engrenagem", "atomo", "mandala", "espectro", "vortice"):
        assert f'def _paint_{style}(' in source


def test_hub_realista_remains_in_561_or_newer():
    from core.version import VERSAO, NOME_PRODUTO
    parts = tuple(int(x) for x in VERSAO.split(".")[:3])
    assert parts >= (5, 6, 0)
    assert NOME_PRODUTO == "T.O.R.V.I.S 2026"
