from pathlib import Path


def test_version_563():
    from core.version import VERSAO
    assert tuple(map(int, VERSAO.split("."))) >= (5, 6, 3)


def test_cowork_fast_plan_covers_common_project_types():
    from actions.dev_agent import _fast_project_plan
    assert _fast_project_plan("crie um aplicativo desktop de notas", "python")["kind"] == "desktop"
    assert _fast_project_plan("crie um site para cadastro", "python")["kind"] == "web"
    assert _fast_project_plan("crie uma API REST para produtos", "python")["kind"] == "api"
    assert _fast_project_plan("faça uma automação para organizar arquivos", "python")["kind"] == "automation"


def test_cowork_fast_plan_falls_back_for_large_architecture():
    from actions.dev_agent import _fast_project_plan
    assert _fast_project_plan("sistema enterprise com microserviços e kubernetes", "python") is None
    assert _fast_project_plan("desktop app", "typescript") is None


def test_fast_bundle_parser_reads_multiple_files():
    from actions.dev_agent import _parse_file_bundle
    raw = "===FILE app.py===\nprint('ok')\n===FILE README.md===\n# App\n"
    got = _parse_file_bundle(raw)
    assert got["app.py"] == "print('ok')"
    assert got["README.md"] == "# App"


def test_cowork_button_uses_fast_profile_and_one_prompt():
    text = Path("gui/window.py").read_text(encoding="utf-8")
    start = text.index("def _start_cowork_no_folder")
    end = text.index("def _start_background_hotkey", start)
    block = text[start:end]
    assert '"profile": "fast"' in block
    assert "Cowork rápido" in block
    assert "Nome do projeto" not in block
    assert "Criando projeto" in block


def test_interface_refinement_is_present():
    window = Path("gui/window.py").read_text(encoding="utf-8")
    widgets = Path("gui/widgets.py").read_text(encoding="utf-8")
    hud = Path("gui/hud.py").read_text(encoding="utf-8")
    assert "def _toggle_content_compact" in window
    assert '"warning"' in window
    assert "◉ ON" in window and "○ OFF" in window
    assert 'HoloPanel("COMANDO", "ENTRADA")' in window
    assert "ENTER para enviar" in window
    assert 'return "you", "VOCÊ"' in widgets
    assert "setBackground(QBrush(blend(C.PRI, 0.13)))" in widgets
    assert "fw * 0.405" in hud
    assert "W * 0.31" in hud


def test_folder_counter_uses_actual_walk_files_variable():
    widgets = Path("gui/widgets.py").read_text(encoding="utf-8")
    assert "n += len(arquivos)" in widgets
    assert "n += len(files)" not in widgets


def test_fast_bundle_writer_writes_all_files_in_one_model_call(tmp_path, monkeypatch):
    import actions.dev_agent as d

    class Response:
        text = "===FILE app.py===\nprint('ok')\n===FILE README.md===\n# App\n"

    class Model:
        calls = 0
        def generate_content(self, prompt):
            self.calls += 1
            return Response()

    model = Model()
    monkeypatch.setattr(d, "_get_model", lambda *_a, **_k: model)
    plan = {
        "files": [
            {"path": "app.py", "description": "app"},
            {"path": "README.md", "description": "docs"},
        ],
        "dependencies": [],
        "run_command": "python app.py",
    }
    got = d._write_project_bundle("teste", "python", plan, tmp_path)
    assert model.calls == 1
    assert set(got) == {"app.py", "README.md"}
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "print('ok')"
