"""Acquire only the official version-3 release; never parse test labels here."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'data/public/scania_component_x/v3'
OUT = ROOT / 'models/public_validation/scania_component_x'
SOURCE = 'https://researchdata.se/en/catalogue/dataset/2024-34'
FILES = [f'{s}_{name}.csv' for s in ('train', 'validation', 'test')
         for name in ('operational_readouts', 'tte' if s == 'train' else 'labels', 'specifications')]
DOCS = ['Scania_Component_X.pdf', '2024_IDA_challenge_v2.pdf']


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def acquire(name):
    kind = 'documentation' if name.endswith('.pdf') else 'data'
    folder = DATA / ('documentation' if kind == 'documentation' else 'raw')
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / name
    url = f'https://api.researchdata.se/dataset/2024-34/3/file/{kind}?filePath={name}'
    if not dest.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'MedOps-Public-Validation/1.0'})
        partial = dest.with_suffix(dest.suffix + '.partial')
        with urllib.request.urlopen(request, timeout=120) as response, partial.open('wb') as f:
            expected = response.headers.get('Content-Length')
            for block in iter(lambda: response.read(4 * 1024 * 1024), b''):
                f.write(block)
        if expected and partial.stat().st_size != int(expected):
            raise RuntimeError(f'Incomplete download: {name}')
        partial.replace(dest)
    result = {'filename': name, 'relative_path': str(dest.relative_to(DATA)),
              'url': url, 'bytes': dest.stat().st_size, 'sha256': sha256(dest),
              'verified_at_utc': datetime.now(timezone.utc).isoformat()}
    print(f'Acquired {name}: {result["bytes"]:,} bytes; SHA256 {result["sha256"]}', flush=True)
    return result


def download():
    if (OUT / 'freeze.json').exists():
        raise RuntimeError('Frozen experiment: refusing to rewrite download manifest')
    if (DATA / 'manifest.json').exists():
        old = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
        for record in old['files']:
            cached = DATA / record['relative_path']
            if cached.exists() and sha256(cached) != record['sha256']:
                raise RuntimeError(f'Cached file changed: {cached.name}; investigate before proceeding')
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(acquire, DOCS + FILES))
    write_json(DATA / 'manifest.json', {
        'dataset': 'SCANIA Component X Dataset', 'version': 3,
        'doi': '10.5878/bnh5-ka77', 'publisher': 'Scania CV AB',
        'repository': 'Swedish National Data Service / Researchdata.se',
        'source': SOURCE, 'license': 'CC BY 4.0',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'attribution': 'Lindgren, Steinert, Andersson Reyna, Kharazian, and Magnusson; Scania CV AB and Stockholm University.',
        'download_date_utc': datetime.now(timezone.utc).isoformat(),
        'files': records, 'test_labels': 'Downloaded as opaque bytes; not parsed before freeze.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', required=True)
    parser.parse_args()
    download()
