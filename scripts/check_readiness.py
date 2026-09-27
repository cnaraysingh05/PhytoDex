"""Show deferred teammate work; --require-team makes missing diagnosis fail CI."""
import argparse
import importlib.util
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

parser = argparse.ArgumentParser()
parser.add_argument('--require-team', action='store_true')
args = parser.parse_args()
diagnosis_ready = importlib.util.find_spec('analysis.diagnosis') is not None
route_ready = importlib.util.find_spec('backend.routes.analysis') is not None
ready = diagnosis_ready and route_ready
print('Photo diagnosis: ' + ('module present; run the tests' if diagnosis_ready else 'PENDING teammate implementation'))
print('Final photo route: ' + ('present' if route_ready else 'PENDING teammate; temporary bridge only'))
print('Frontend: teammate-owned; browser and Pi testing still required.')
if not ready and args.require_team:
    raise SystemExit('Cannot mark the combined application ready without the teammate diagnosis module and final analysis route.')
