import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services import assistant  # Loads .env.ai consistently.
from backend.services.vision import get_model

p = argparse.ArgumentParser()
p.add_argument('image', type=Path)
args = p.parse_args()
print(json.dumps(get_model().identify(args.image), indent=2))
