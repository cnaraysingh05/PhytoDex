"""One explicitly requested live call; does not claim final diagnosis integration."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.classifier import classify_leaf, AnalysisError

parser = argparse.ArgumentParser()
parser.add_argument('--image', type=Path, required=True)
parser.add_argument('--live', action='store_true')
args = parser.parse_args()
if not args.live:
    raise SystemExit('Add --live to send this photo to Gemini. Offline validation uses pytest.')
try:
    with args.image.open('rb') as f:
        raw = classify_leaf(f.read(10 * 1024 * 1024 + 1))
except (AnalysisError, OSError) as exc:
    raise SystemExit(str(exc))
print(json.dumps({'source': 'gemini', 'stage': 'raw_observations', 'observations': raw}, indent=2))
print('Provider check only. The teammate diagnosis module and final route still need integration.')
