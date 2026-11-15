"""Fast Cowork regressions. No real model calls or network are needed."""
from pathlib import Path
from threading import Barrier, Lock
import pytest


def test_safe_model_plan_blocks_absolute_escape_and_duplicates():
    from actions.dev_agent import _safe_file_plan
    for bad in ('../secrets.txt', 'C:\\Windows\\test.py', '/tmp/test.py',
                'foo/../../secret', 'foo//bar.py', 'foo/./bar.py'):
        with pytest.raises(ValueError):
            _safe_file_plan({'files': [{'path': bad}]})
    with pytest.raises(ValueError):
        _safe_file_plan({'files': [{'path': 'A.py'}, {'path': 'a.py'}]})
    assert _safe_file_plan({'files': [{'path': 'src\\main.py'}]})[0]['path'] == 'src/main.py'


def test_dependency_waves_do_not_parallelize_dependents():
    from actions.dev_agent import _generation_waves
    files = [
        {'path': 'app.py', 'imports': ['utils.helpers']},
        {'path': 'README.md', 'imports': []},
        {'path': 'utils/helpers.py', 'imports': []},
        {'path': 'config.py', 'imports': []},
    ]
    waves = [[f['path'] for f in wave] for wave in _generation_waves(files)]
    assert set(waves[0]) == {'README.md', 'utils/helpers.py', 'config.py'}
    assert waves[1] == ['app.py']


def test_auto_fast_profile_for_simple_projects(monkeypatch):
    import actions.dev_agent as d
    chosen = []
    monkeypatch.setattr(d, '_start_build', lambda *a, **kw: chosen.append(kw['fast']) or 'ok')
    for request, profile, expected in [
        ('crie um script simples', '', True),
        ('crie um script simples', 'full', False),
        ('sistema enterprise de microserviços', '', False),
        ('crie um script simples', 'fast', True),
    ]:
        assert d.dev_agent({'description': request, 'profile': profile}) == 'ok'
        assert chosen[-1] is expected


def test_fast_fallback_writes_independent_files_concurrently(tmp_path, monkeypatch):
    import actions.dev_agent as d
    gate = Barrier(2)
    monkeypatch.setattr(d, 'PROJECTS_DIR', tmp_path)
    monkeypatch.setattr(d, '_write_project_bundle', lambda *a: {})
    monkeypatch.setattr(d, '_write_file', lambda fi, *a, **kw: 'unused')  # replaced below
    started = []
    mutex = Lock()

    def write(file_info, *args, **kwargs):
        with mutex:
            started.append(file_info['path'])
        gate.wait(timeout=5)  # fails if two files aren't genuinely concurrent
        return "print('ok')" if file_info['path'].endswith('.py') else '# Documentation'

    monkeypatch.setattr(d, '_write_file', write)
    monkeypatch.setattr(d, '_run_project', lambda *a, **kw: 'Ran with no output.')
    monkeypatch.setattr(d, '_open_vscode', lambda *a: True)
    result = d._build_project('crie um script de exemplo', 'python', 'test', 10, fast=True)
    assert 'is working' in result
    assert set(started) == {'main.py', 'README.md'}


def test_failed_file_is_never_reported_as_success(tmp_path, monkeypatch):
    import actions.dev_agent as d
    monkeypatch.setattr(d, 'PROJECTS_DIR', tmp_path)
    monkeypatch.setattr(d, '_write_project_bundle', lambda *a: {})
    def write(file_info, *a, **kw):
        if file_info['path'] == 'README.md':
            raise RuntimeError('unavailable')
        return "print('ok')"
    monkeypatch.setattr(d, '_write_file', write)
    monkeypatch.setattr(d, '_run_project', lambda *a, **kw: pytest.fail('must not run incomplete project'))
    result = d._build_project('crie um script de exemplo', 'python', 'test', 10, fast=True)
    assert 'partially created' in result and 'README.md' in result
    assert 'working' not in result
