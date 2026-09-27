"""Store guidance and fallback responses in the shared database."""
import json
from backend.models.db import get_db


def log_assistant_query(species, message, response, source='gemini'):
    conn = get_db()
    try:
        with conn:
            cursor = conn.execute(
                'INSERT INTO assistant_logs(species,message,response_json,source) VALUES(?,?,?,?)',
                (species, message, json.dumps(response), source))
        return cursor.lastrowid
    finally:
        conn.close()


def list_assistant_logs(limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('limit must be an integer between 1 and 100')
    conn = get_db()
    try:
        rows = conn.execute('SELECT * FROM assistant_logs ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        result = []
        for row in rows:
            entry = dict(row)
            entry['response'] = json.loads(entry.pop('response_json'))
            result.append(entry)
        return result
    finally:
        conn.close()
