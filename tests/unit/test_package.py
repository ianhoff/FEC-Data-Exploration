import json
from pathlib import Path
import subprocess
import sys

from fec_explorer.paths import project_root


def test_installed_package_imports_outside_checkout(tmp_path):
    code = '''import json, fec_explorer
from importlib.resources import files
from fec_explorer.paths import PROJECT_ROOT
resource = files('fec_explorer.resources').joinpath('us-states-10m.json')
print(json.dumps({'package': fec_explorer.__file__, 'has_states': 'states' in json.loads(resource.read_text())['objects'], 'root': str(PROJECT_ROOT)}))'''
    result = subprocess.run([sys.executable, '-I', '-c', code], cwd=tmp_path,
                            capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    assert data['has_states']
    assert Path(data['package']).parent.name == 'fec_explorer'
    assert Path(data['root']) == Path(__file__).resolve().parents[2]


def test_project_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv('FEC_PROJECT_DIR', str(tmp_path))
    assert project_root() == tmp_path.resolve()
