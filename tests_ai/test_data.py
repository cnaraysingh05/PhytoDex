import tempfile
import unittest
from pathlib import Path
from PIL import Image
from ml.prepare_data import prepare


class DataTests(unittest.TestCase):
    def test_groups_and_duplicates_do_not_leak(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for class_id, label in enumerate(['rose', 'daisy']):
                for group in range(10):
                    path = root / 'raw' / label / f'plant{group}'
                    path.mkdir(parents=True)
                    for i in range(2):
                        Image.new('RGB', (20, 20), (class_id * 100, group * 20, i * 100)).save(path / f'{i}.png')
                duplicate = root / 'raw' / label / 'duplicate.png'
                duplicate.write_bytes((root / 'raw' / label / 'plant0/0.png').read_bytes())
            manifest = prepare(root / 'raw', root / 'manifest.json')
            self.assertEqual(manifest['duplicates_removed'], 2)
            seen = {}
            hashes = set()
            for row in manifest['records']:
                key = row['label'], row['group']
                self.assertEqual(seen.setdefault(key, row['split']), row['split'])
                self.assertNotIn(row['pixel_sha256'], hashes)
                hashes.add(row['pixel_sha256'])
            for split in ['train', 'val', 'test']:
                self.assertEqual({r['label'] for r in manifest['records'] if r['split'] == split}, {'rose', 'daisy'})


if __name__ == '__main__':
    unittest.main()
