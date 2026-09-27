"""My Garden scan history, stored in the photo_assessments table.

  * species      -- a row in `plants` (the PlantDex library)
  * garden plant -- a row in `garden`: one plant the user owns. Its plant_id is
                    always the species the user chose; nothing here guesses it.
  * scan         -- a photo_assessments row linked to a garden plant. Scans are
                    only ever added, never overwritten.
"""
import json

ASSESSMENT_FIELDS = ('plant_name', 'scientific_name', 'health_rating', 'visible_signs',
                     'possible_causes', 'certainty', 'limitations', 'next_steps', 'source')
COMPARISON_NOTE = ('Each scan is a separate photo assessment. Lighting, angle, and distance '
                   'change how a plant looks, so treat differences as a reason to look '
                   'closer, not as a measurement.')

# Same columns as GET /api/garden in backend/routes/garden.py (read-only here).
GARDEN_SELECT = """
    SELECT garden.id, garden.plant_id, garden.nickname, garden.date_added,
           garden.notes, garden.last_watered, garden.created_at,
           plants.common_name, plants.scientific_name, plants.image_url
    FROM garden
    JOIN plants ON garden.plant_id = plants.id
"""


def load_assessment(conn, capture_id):
    row = conn.execute('SELECT garden_id, assessment_json FROM photo_assessments '
                       'WHERE capture_id = ?', (capture_id,)).fetchone()
    if row is None:
        return None
    return {'garden_id': row['garden_id'], 'assessment': json.loads(row['assessment_json'])}


def save_assessment(conn, capture_id, assessment):
    """Store (or refresh) an unsaved scan's assessment. A scan already in a
    garden plant's history is left untouched."""
    conn.execute(
        'INSERT INTO photo_assessments (capture_id, assessment_json) VALUES (?, ?) '
        'ON CONFLICT(capture_id) DO UPDATE SET assessment_json = excluded.assessment_json, '
        "created_at = datetime('now') WHERE photo_assessments.garden_id IS NULL",
        (capture_id, json.dumps(assessment)),
    )
    conn.commit()


def attach_scan(conn, capture_id, garden_id):
    """Link an assessed scan to a garden plant. Returns False if it is already
    linked to a plant (a photo belongs to one plant only)."""
    changed = conn.execute(
        'UPDATE photo_assessments SET garden_id = ? WHERE capture_id = ? AND garden_id IS NULL',
        (garden_id, capture_id),
    ).rowcount
    conn.commit()
    return changed == 1


def list_scans(conn, garden_id):
    """Every scan of one garden plant, newest first."""
    rows = conn.execute(
        'SELECT captures.id, captures.image_url, captures.created_at, '
        'photo_assessments.assessment_json FROM photo_assessments '
        'JOIN captures ON captures.id = photo_assessments.capture_id '
        'WHERE photo_assessments.garden_id = ? '
        'ORDER BY captures.created_at DESC, captures.id DESC',
        (garden_id,),
    ).fetchall()
    scans = []
    for row in rows:
        assessment = json.loads(row['assessment_json'])
        scan = {'capture_id': row['id'], 'image_url': row['image_url'],
                'scanned_at': row['created_at']}
        scan.update({field: assessment.get(field) for field in ASSESSMENT_FIELDS})
        scans.append(scan)
    return scans


def scan_summaries(conn):
    """{garden_id: {"scan_count", "latest_scan"}} for every garden plant with scans."""
    rows = conn.execute('SELECT DISTINCT garden_id FROM photo_assessments '
                        'WHERE garden_id IS NOT NULL').fetchall()
    summaries = {}
    for row in rows:
        entry = add_scan_summary(conn, {'id': row['garden_id']})
        summaries[row['garden_id']] = {'scan_count': entry['scan_count'],
                                       'latest_scan': entry['latest_scan']}
    return summaries


def add_scan_summary(conn, entry, include_history=False):
    """Add scan_count and latest_scan (and optionally the full history) to a
    garden entry dict. Existing garden fields are not changed."""
    scans = list_scans(conn, entry['id'])
    entry['scan_count'] = len(scans)
    latest = scans[0] if scans else None
    entry['latest_scan'] = None if latest is None else {
        key: latest[key] for key in ('capture_id', 'image_url', 'scanned_at', 'health_rating')}
    if include_history:
        entry['scans'] = scans
        entry['comparison'] = None
        if len(scans) >= 2:
            pick = ('capture_id', 'scanned_at', 'health_rating', 'visible_signs', 'certainty')
            entry['comparison'] = {
                'previous': {key: scans[1][key] for key in pick},
                'current': {key: scans[0][key] for key in pick},
                'note': COMPARISON_NOTE,
            }
    return entry


def get_garden_plant(conn, garden_id):
    """One garden plant with its dated scan history, or None."""
    row = conn.execute(GARDEN_SELECT + ' WHERE garden.id = ?', (garden_id,)).fetchone()
    return None if row is None else add_scan_summary(conn, dict(row), include_history=True)
