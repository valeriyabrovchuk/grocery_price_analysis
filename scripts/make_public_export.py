"""Create a reviewable source ZIP without Git history or local backups.

Run only after validation. This does not publish or create any Git commits.
"""
import hashlib
import json
from pathlib import Path
import zipfile

try:
    from .audit_repository import inspect_content, SECRET_KINDS
except ImportError:
    from audit_repository import inspect_content, SECRET_KINDS
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ['notebooks', 'scripts', 'data/processed', 'data/reference', 'reports', 'docs', 'archive']
ROOT_FILES = ['README.md', 'AGENTS.md', '.gitignore', 'requirements.txt', 'requirements-lock.txt',
              'data/raw/README.md', 'data/interim/README.md']


def public_files():
    paths = [ROOT / name for name in ROOT_FILES]
    for folder in FOLDERS:
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and
                     '__pycache__' not in p.parts and '.ipynb_checkpoints' not in p.parts and p.suffix not in ['.pyc', '.zip'])
    return sorted(set(p for p in paths if p.exists()))


def main():
    files = public_files()
    findings, counts = [], Counter()
    for p in files:
        inspect_content(p.read_bytes(), p.relative_to(ROOT).as_posix(), findings, counts)
    unsafe = [f for f in findings if f['kind'] in SECRET_KINDS or f['kind'] == 'local_user_path']
    if unsafe:
        print(json.dumps(unsafe, ensure_ascii=False, indent=2))
        raise ValueError('Export contains a credential candidate or local personal path; inspect before publishing.')
    target = ROOT / '.local_archive' / 'grocery_price_analysis_public.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, arcname='grocery_price_analysis/' + p.relative_to(ROOT).as_posix())
    print('Public export:', target.name, 'files:', len(files), 'bytes:', target.stat().st_size)
    print('SHA256:', hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
