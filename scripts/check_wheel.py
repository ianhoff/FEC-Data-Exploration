"""Check a built wheel, including resource loading from outside the checkout."""
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    wheel = Path(sys.argv[1]).resolve()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert 'fec_explorer/resources/us-states-10m.json' in names
        assert 'fec_explorer/resources/us-atlas-LICENSE' in names
        assert not any(Path(n).name in ('config.json','config.analysis.json','pgpass.conf') for n in names)
    code = '''import sys, json
sys.path.insert(0, sys.argv[1])
import fec_explorer
assert '.whl' in fec_explorer.__file__
from fec_explorer.origins import STATES, choropleth
chart=choropleth(STATES.assign(records=1, recorded_amount=1.0), 'Record count')
assert chart.to_dict()['projection']['type']=='albersUsa'
print('PASS: built wheel imports and loads map resources outside checkout.')'''
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run([sys.executable,'-I','-c',code,str(wheel)],cwd=directory,check=True)


if __name__=='__main__':main()
