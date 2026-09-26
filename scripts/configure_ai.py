"""Write private .env.ai without putting credentials in shell history."""
import getpass
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / '.env.ai'
if target.exists():
    raise SystemExit('.env.ai already exists. Edit it locally; this tool will not overwrite it.')
key = getpass.getpass('Gemini API key (Enter for offline mode): ').strip()
model = input('Gemini model [gemini-3.8-flash]: ').strip() or 'gemini-3.8-flash'
if any(c in key + model for c in '\r\n\"\''):
    raise SystemExit('Unexpected characters in key or model')
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(f'AI_MODE={"gemini" if key else "offline"}\nGEMINI_API_KEY={key}\n'
            f'GEMINI_MODEL={model}\nVISION_MODEL_DIR=models/flowers\n')
print('Created private .env.ai. Restart your server after configuration changes.')
