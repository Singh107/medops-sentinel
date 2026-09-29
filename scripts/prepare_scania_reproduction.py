"""Stage original Scania source in a new workspace; never run the experiment."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def prepare(name):
    if not name or name in {'.', '..'} or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
        raise ValueError('Use a simple run name containing letters, numbers, hyphens or underscores')
    destination = ROOT / 'reproductions' / name
    destination.mkdir(parents=True, exist_ok=False)
    package = destination / 'ml' / 'public_validation' / 'scania_component_x'
    package.mkdir(parents=True)
    shutil.copy2(ROOT / 'ml' / '__init__.py', destination / 'ml' / '__init__.py')
    source = ROOT / 'ml' / 'public_validation' / 'scania_component_x'
    for path in source.iterdir():
        if path.is_file() and path.suffix in {'.py', '.md', '.txt'}:
            shutil.copy2(path, package / path.name)
    print(f'Staged source only: {destination}')
    print('No data, accepted evidence, environment, downloads or model execution copied/run.')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name', help='New independent run directory under reproductions/')
    prepare(parser.parse_args().name)
