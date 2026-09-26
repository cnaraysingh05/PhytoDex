"""One live/offline call; exits nonzero if live mode silently falls back."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services.assistant import get_plant_guidance

result = get_plant_guidance('Pothos', 'Leaves are yellow and the soil has stayed wet for a week.')
print(json.dumps(result, indent=2))
if os.getenv('AI_MODE', 'offline') == 'gemini' and result['source'] != 'gemini':
    raise SystemExit('Live check failed. Check the key, model access, quota and network in AI Studio.')
