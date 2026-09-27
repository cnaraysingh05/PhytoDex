"""Opt-in dependency merge for the inspected Flask scaffold."""
import re
from pathlib import Path
path = Path(__file__).resolve().parents[1] / 'requirements.txt'
if not path.exists():
    raise SystemExit('No team requirements.txt yet. Use requirements-ai.txt directly.')
lines = path.read_text().splitlines()
updated = [line for line in lines if not re.match(r'^flask\s*(?:[<=>!~;]|$)', line, re.I)]
if '-r requirements-ai.txt' not in updated:
    updated.append('-r requirements-ai.txt')
path.write_text('\n'.join(updated) + '\n')
print('Included AI requirements and moved the Flask version constraint there. Review the diff.')
