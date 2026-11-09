"""Audit Git's publication candidates without reading ignored local credentials/data."""
from pathlib import Path
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
DENIED_NAMES={'config.json','config.analysis.json','pgpass.conf','.pgpass','secrets.toml',
              'source_quality_report.json','database_quality_report.json','origins_validation.json'}
PATTERNS={
    'private key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'GitHub token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'AWS access key':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'credential URL':re.compile(r'postgres(?:ql)?://[^\s/:]+:[^\s@]+@'),
}


def main():
    result=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],
                          cwd=ROOT,capture_output=True,check=True)
    paths=sorted(set(p for p in result.stdout.decode('utf-8').split('\0') if p))
    findings=[]
    for name in paths:
        path=Path(name)
        if path.name in DENIED_NAMES or any(part in {'.venv','data','.test-postgres','test-results','__pycache__'} for part in path.parts) or path.suffix in {'.zip','.part','.pem','.key'}:
            findings.append((name,'local-only or sensitive file is a publication candidate'))
            continue
        absolute=ROOT/path
        if absolute.stat().st_size>10*1024*1024:
            findings.append((name,'unexpectedly large file'))
        if path.suffix.lower() not in {'.py','.json','.md','.yml','.yaml','.toml','.txt','.ini',''}:
            continue
        text=absolute.read_text(encoding='utf-8')
        for label,pattern in PATTERNS.items():
            if pattern.search(text):findings.append((name,label))
    for example in ('config.example.json','config.analysis.example.json'):
        if any('password' in key.lower() for key in json.loads((ROOT/example).read_text())):
            findings.append((example,'password key in example config'))
    for name,label in findings:
        print(f'FAIL: {name}: {label}')
    if findings:raise SystemExit(1)
    print(f'PASS: {len(paths)} Git publication candidates checked; no blocked files or credential-pattern matches.')
    print('This targeted check is not a guarantee against every possible secret. Review git diff --cached before pushing.')


if __name__=='__main__':main()
