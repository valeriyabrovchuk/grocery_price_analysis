"""Read-only content audit. Reports locations, never secret values.

Uses only Python's standard library; includes reachable refs and reflogs.
This is a pattern scan, not a guarantee that a repository contains no secrets.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '.venv', '.venv-portfolio', '.local_archive', '__pycache__', '.ipynb_checkpoints'}
PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'github_token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'aws_access_key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'service_token': re.compile(r'\b(?:xox[baprs]-[A-Za-z0-9-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{32,})'),
    'credential_assignment': re.compile(r'''(?im)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[=:]\s*["']([^"'\r\n]{8,})["']'''),
    'local_user_path': re.compile(r'(?i)(?:[A-Z]:[\\/]+Users[\\/]+[^\\/\s"\']+|/(?:Users|home)/[^/\s"\']+)'),
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
}
SECRET_KINDS = {'private_key', 'github_token', 'aws_access_key', 'service_token', 'credential_assignment'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def inspect_content(data, location, findings, counts):
    # Office documents are ZIP containers: inspect XML and metadata too.
    if data.startswith(b'PK\x03\x04'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for entry in z.infolist():
                    if entry.filename.endswith(('.xml', '.rels', '.txt', '.csv')):
                        inspect_content(z.read(entry), location + '::' + entry.filename, findings, counts)
            return
        except (zipfile.BadZipFile, RuntimeError):
            counts['unreadable_archives'] += 1
    if b'\x00' in data[:2000]:
        counts['binary_items_not_text_scanned'] += 1
        return
    text = data.decode('utf-8-sig', errors='replace')
    for kind, pattern in PATTERNS.items():
        matches = list(pattern.finditer(text))
        if matches:
            findings.append({'kind': kind, 'location': location,
                             'occurrences': len(matches),
                             'first_line': text.count('\n', 0, matches[0].start()) + 1})


def audit():
    findings, counts, inventory = [], Counter(), []
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or any(part in SKIP for part in p.relative_to(ROOT).parts):
            continue
        data = p.read_bytes()
        rel = p.relative_to(ROOT).as_posix()
        inventory.append({'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        inspect_content(data, 'worktree:' + rel, findings, counts)
    objects = git('rev-list', '--objects', '--all', '--reflog').decode('utf-8', errors='replace').splitlines()
    metadata = subprocess.run(['git', 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)'],
                              input=('\n'.join(line.split(' ', 1)[0] for line in objects) + '\n').encode(),
                              cwd=ROOT, capture_output=True, check=True).stdout.decode().splitlines()
    blob_objects = [(line.split(' ', 1), meta.split()) for line, meta in zip(objects, metadata)
                    if len(meta.split()) == 3 and meta.split()[1] == 'blob']
    process = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for names, meta in blob_objects:
        sha = names[0]
        path = names[1] if len(names) > 1 else '(path unavailable)'
        process.stdin.write((sha + '\n').encode()); process.stdin.flush()
        header = process.stdout.readline().split()
        size = int(header[2])
        data = process.stdout.read(size); process.stdout.read(1)
        inspect_content(data, f'git:{sha}:{path}', findings, counts)
    process.stdin.close(); process.wait()
    counts['git_unique_blobs'] = len(blob_objects)
    counts['worktree_files'] = len(inventory)
    counts['commits_including_reflogs'] = int(git('rev-list', '--all', '--reflog', '--count'))
    counts['git_author_identities'] = len(set(git('log', '--all', '--reflog', '--format=%an <%ae>').splitlines()))
    report = {'scope': 'Working files, Office XML, all local refs, stash and reflogs; no remote fetch.',
              'limitations': 'Pattern scan only; binary images/compiled objects and unknown credentials are not exhaustively inspected. Git author identity remains in history.',
              'counts': dict(counts), 'secret_candidate_locations': [x for x in findings if x['kind'] in SECRET_KINDS],
              'privacy_locations': [x for x in findings if x['kind'] not in SECRET_KINDS]}
    return report, inventory


if __name__ == '__main__':
    report, inventory = audit()
    target = ROOT / '.local_archive' / 'audit'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'security_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (target / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'counts': report['counts'], 'secret_candidates': len(report['secret_candidate_locations']),
                      'privacy_locations': len(report['privacy_locations'])}, indent=2))
