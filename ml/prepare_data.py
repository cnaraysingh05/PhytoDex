"""Download official flower photos or split a user-owned class-folder dataset."""
import argparse
import hashlib
import json
import random
import tarfile
import urllib.request
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageOps

URL = 'https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz'


def prepare(source, output, seed=42, min_images=20, provenance=None):
    source, output = Path(source).resolve(), Path(output)
    if output.exists():
        raise ValueError('Output exists; choose a new manifest path to preserve your split.')
    labels = sorted(p.name for p in source.iterdir() if p.is_dir() and not p.name.startswith('.'))
    if len(labels) < 2:
        raise ValueError('Need at least two class folders')
    seen, records, duplicates = {}, [], 0
    rng = random.Random(seed)
    for label in labels:
        groups = defaultdict(list)
        parents = {}
        digest_groups = {}
        def find(group):
            parents.setdefault(group, group)
            if parents[group] != group:
                parents[group] = find(parents[group])
            return parents[group]
        for path in sorted((source / label).rglob('*')):
            if path.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                continue
            with Image.open(path) as original:
                im = ImageOps.exif_transpose(original).convert('RGB')
                digest = hashlib.sha256(str(im.size).encode() + im.tobytes()).hexdigest()
            rel = path.relative_to(source / label)
            group = rel.parts[0] if len(rel.parts) > 1 else path.stem.split('__')[0]
            find(group)
            if digest in seen:
                if seen[digest] != label:
                    raise ValueError(f'Identical image has conflicting labels: {path}')
                parents[find(group)] = find(digest_groups[digest])
                duplicates += 1
                continue
            seen[digest] = label
            digest_groups[digest] = group
            groups[group].append({'path': str(path.relative_to(source)), 'label': label,
                                  'group': group, 'pixel_sha256': digest})
        merged = defaultdict(list)
        for group, items in groups.items():
            merged[find(group)].extend(items)
        groups = merged
        names = sorted(groups)
        if len(names) < 5 or sum(map(len, groups.values())) < min_images:
            raise ValueError(f'{label}: need >=5 groups and >={min_images} images')
        rng.shuffle(names)
        holdout = max(1, int(len(names) * .15))
        for i, name in enumerate(names):
            split = 'test' if i < holdout else 'val' if i < 2 * holdout else 'train'
            records.extend(dict(r, split=split) for r in groups[name])
    manifest = {'root': str(source), 'labels': labels, 'seed': seed,
                'provenance': provenance or {'type': 'custom', 'license': 'Record your image sources and permissions'},
                'duplicates_removed': duplicates, 'records': records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2))
    counts = {s: sum(r['split'] == s for r in records) for s in ('train', 'val', 'test')}
    print(json.dumps({'labels': labels, 'counts': counts, 'duplicates_removed': duplicates}, indent=2))
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, help='Class-folder dataset; omit to download flowers')
    p.add_argument('--out', type=Path, default=Path('ml/data/manifest.json'))
    args = p.parse_args()
    provenance = None
    if args.source is None:
        cache = Path('ml/data').resolve()
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / 'flower_photos.tgz'
        if not archive.exists():
            print('Downloading official flower photos (~218 MiB)...')
            temp = archive.with_suffix('.download')
            urllib.request.urlretrieve(URL, temp)
            temp.replace(archive)
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            for member in members:
                target = (cache / member.name).resolve()
                if not target.is_relative_to(cache) or not (member.isfile() or member.isdir()):
                    raise ValueError('Unsafe archive entry')
            tar.extractall(cache, members=members, filter='data')
        args.source = cache / 'flower_photos'
        provenance = {
            'url': URL, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'license_file': 'flower_photos/LICENSE.txt',
            'scope': 'Five flower categories; not general plant species identification',
        }
        (cache / 'source.json').write_text(json.dumps(provenance, indent=2))
    prepare(args.source, args.out, provenance=provenance)


if __name__ == '__main__':
    main()
