import json
import sqlite3

import pytest
from app import create_app
from backend.models.db import init_db, get_db, database_path, SCHEMA_PATH
from backend.models.migrations import allow_unknown_species


def test_unknown_plant_save_history_restart_delete():
    init_db()
    client = create_app({'TESTING': True}).test_client()
    response = client.post('/api/garden', json={'nickname': 'Mystery plant', 'notes': 'Window'})
    assert response.status_code == 201
    gid = response.json['id']
    assert response.json['plant_id'] is None
    conn = get_db()
    cid = conn.execute("INSERT INTO captures(filename,image_url) VALUES ('test.jpg','/test.jpg')").lastrowid
    conn.execute('INSERT INTO photo_assessments(capture_id,assessment_json) VALUES (?,?)',
                 (cid, json.dumps({'plant_name': 'Tentative guess', 'source': 'gemini'})))
    conn.commit(); conn.close()
    assert client.post(f'/api/garden/{gid}/scans', json={'capture_id': cid}).status_code == 201
    init_db()
    client = create_app({'TESTING': True}).test_client()
    assert client.get('/api/garden').json[0]['id'] == gid
    detail = client.get(f'/api/garden/{gid}').json
    assert detail['common_name'] is None
    assert detail['notes'] == 'Window'
    assert detail['scans'][0]['plant_name'] == 'Tentative guess'
    assert client.delete(f'/api/garden/{gid}').status_code == 200
    conn = get_db()
    assert conn.execute('SELECT garden_id FROM photo_assessments').fetchone()[0] is None
    conn.close()


@pytest.mark.parametrize('payload', [[], {}, {'plant_id': True}, {'plant_id': 0},
    {'plant_id': '1'}, {'nickname': '   '}, {'nickname': 123}, {'nickname': 'x'*61}])
def test_invalid_optional_species_inputs(payload):
    init_db()
    client = create_app({'TESTING': True}).test_client()
    assert client.post('/api/garden', json=payload).status_code == 400


def test_existing_database_migration_preserves_links_and_sequence():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_PATH.read_text().replace('plant_id INTEGER,', 'plant_id INTEGER NOT NULL,'))
    conn.execute("INSERT INTO plants(id,common_name) VALUES (7,'Pothos')")
    conn.execute("INSERT INTO garden(id,plant_id,nickname,notes) VALUES (12,7,'Original','Keep me')")
    conn.execute("INSERT INTO garden(id,plant_id) VALUES (99,7)")
    conn.execute('DELETE FROM garden WHERE id=99')
    conn.execute("INSERT INTO captures(id,filename,image_url) VALUES (5,'leaf.jpg','/leaf.jpg')")
    conn.execute("INSERT INTO photo_assessments(capture_id,garden_id,assessment_json) VALUES (5,12,'{}')")
    conn.commit();conn.close()
    init_db();init_db()
    conn = get_db()
    assert tuple(conn.execute('SELECT id,plant_id,nickname,notes FROM garden').fetchone()) == (12,7,'Original','Keep me')
    assert conn.execute('SELECT garden_id FROM photo_assessments').fetchone()[0] == 12
    assert conn.execute("INSERT INTO garden(nickname) VALUES ('Unknown')").lastrowid > 99
    assert not conn.execute('PRAGMA foreign_key_check').fetchall()
    conn.commit();conn.close()
    backups = list(path.parent.glob(path.name + '.before-optional-species-*.bak'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as old:
        assert old.execute('SELECT garden_id FROM photo_assessments').fetchone()[0] == 12
        assert next(r for r in old.execute('PRAGMA table_info(garden)') if r[1]=='plant_id')[3] == 1
