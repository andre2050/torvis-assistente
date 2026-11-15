import time
from pathlib import Path


def test_release_version_565():
    from core.version import VERSAO
    assert tuple(map(int, VERSAO.split('.'))) >= (5, 6, 5)


def test_new_job_has_liveness_fields(tmp_path):
    import actions.dev_agent as d
    d._new_job(tmp_path / 'demo', 'model', 'criar app', None, kind='build')
    snap = d._job_snapshot()
    assert snap['heartbeat'] > 0
    assert snap['last_activity'] > 0
    assert snap['status_detail']


def test_fast_build_falls_back_when_bundle_times_out(tmp_path, monkeypatch):
    import actions.dev_agent as d
    monkeypatch.setattr(d, 'PROJECTS_DIR', tmp_path)
    monkeypatch.setattr(d, '_write_project_bundle', lambda *a, **k: (_ for _ in ()).throw(TimeoutError('stalled')))
    monkeypatch.setattr(d, '_write_file', lambda file_info, **kwargs: "print('ok')" if file_info['path'].endswith('.py') else '# docs')
    monkeypatch.setattr(d, '_run_project', lambda *a, **k: 'Ran with no output.')
    monkeypatch.setattr(d, '_open_vscode', lambda *a, **k: True)
    d._new_job(tmp_path / 'demo', 'model', 'crie um app desktop', None, kind='build')
    result = d._build_project('crie um app desktop', 'python', 'demo', 30, fast=True)
    assert 'is working' in result
    assert (tmp_path / 'demo').exists()


def test_fast_writer_receives_fast_deadline(tmp_path, monkeypatch):
    import actions.dev_agent as d
    seen = {}
    def fake_model_text(prompt, **kwargs):
        seen.update(kwargs)
        return "print('ok')"
    monkeypatch.setattr(d, '_model_text', fake_model_text)
    code = d._write_file(
        {'path':'main.py','description':'main','imports':[]},
        'demo', [{'path':'main.py','description':'main','imports':[]}],
        'python', tmp_path, {}, fast=True,
    )
    assert code == "print('ok')"
    assert seen['fast'] is True


def test_code_agent_ui_shows_liveness_marker():
    src = Path('gui/window.py').read_text(encoding='utf-8')
    assert 'status_detail' in src
    assert '● {live_text}' in src
    assert 'ATIVO' in src and 'AGUARDANDO' in src
