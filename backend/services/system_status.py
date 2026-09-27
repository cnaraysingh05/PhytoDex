"""Real host telemetry; unavailable sensors are null, never simulated data."""
import os
import socket
import time
from pathlib import Path
import psutil
from backend.models.db import database_path, get_db


def cpu_temperature():
    for zone in sorted(Path('/sys/class/thermal').glob('thermal_zone*')):
        try:
            kind = (zone / 'type').read_text().strip().lower()
            if any(word in kind for word in ('cpu', 'soc', 'bcm')):
                value = float((zone / 'temp').read_text()) / 1000
                if -20 <= value <= 150:
                    return round(value, 1)
        except (OSError, ValueError):
            continue
    return None


def database_status():
    if not database_path().is_file():
        return 'not_initialized'
    try:
        conn = get_db()
        try:
            found = {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return 'ok' if {'plants', 'garden', 'captures', 'assistant_logs'} <= found else 'schema_incomplete'
        finally:
            conn.close()
    except Exception:
        return 'unavailable'


def uptime_seconds():
    try:
        return max(0, int(float(Path('/proc/uptime').read_text().split()[0])))
    except (OSError, ValueError, IndexError):
        try:
            return max(0, int(time.time() - psutil.boot_time()))
        except (OSError, psutil.Error):
            return None


def network_interfaces():
    interfaces = []
    stats = psutil.net_if_stats()
    for name, addresses in psutil.net_if_addrs().items():
        if name not in stats or not stats[name].isup:
            continue
        ips = [a.address for a in addresses if a.family == socket.AF_INET and not a.address.startswith('127.')]
        if ips:
            interfaces.append({'name': name, 'ipv4': ips})
    return interfaces


def system_status():
    try:
        interfaces = network_interfaces()
        network_status = 'local_interface_up' if interfaces else 'no_local_ipv4'
    except (OSError, psutil.Error):
        interfaces, network_status = [], 'unavailable'
    try:
        hardware = Path('/proc/device-tree/model').read_text().rstrip('\x00\n')
    except OSError:
        hardware = None
    mode = os.getenv('AI_MODE', 'offline').lower()
    configured = bool(os.getenv('GEMINI_API_KEY', '').strip() and os.getenv('GEMINI_MODEL', '').strip())
    return {
        'hostname': socket.gethostname(), 'hardware_model': hardware,
        'is_raspberry_pi': bool(hardware and 'raspberry pi' in hardware.lower()),
        'uptime_seconds': uptime_seconds(),
        'cpu_temperature_c': cpu_temperature(),
        'backend': {'status': 'ok'}, 'database': {'status': database_status()},
        'network': {'status': network_status,
                    'interfaces': interfaces, 'internet_status': 'not_checked'},
        'gemini': {'mode': mode, 'model': os.getenv('GEMINI_MODEL') or None,
                   'status': 'offline' if mode == 'offline' else
                   'configured_not_checked' if configured and mode == 'gemini' else 'not_configured'},
    }
