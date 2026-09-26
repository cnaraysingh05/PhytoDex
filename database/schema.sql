-- PhytoDex database schema
-- Owner: Person 2 (Backend / Database / API) -- feature/backend

CREATE TABLE IF NOT EXISTS plants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    common_name TEXT NOT NULL,
    scientific_name TEXT,
    category TEXT,
    water TEXT,
    light TEXT,
    soil TEXT,
    temperature TEXT,
    difficulty TEXT,
    summary TEXT,
    image_url TEXT
);

CREATE TABLE IF NOT EXISTS garden (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL,
    nickname TEXT,
    date_added TEXT DEFAULT (datetime('now')),
    notes TEXT,
    last_watered TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (plant_id) REFERENCES plants(id)
);

-- NOT in the original team contract (Section 7/8). Added to support the
-- stretch camera-capture upload flow. Flag to Person 3 (frontend) and
-- Person 4 (AI) before merging -- Person 4's identification step will read
-- rows from this table via capture_id/image_url.
CREATE TABLE IF NOT EXISTS captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    image_url TEXT NOT NULL,
    status TEXT DEFAULT 'pending',   -- pending -> stored -> identified (Person 4 owns the last transition)
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assistant_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species TEXT,
    message TEXT NOT NULL,
    response_json TEXT NOT NULL,
    source TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_assistant_logs_created_at ON assistant_logs(created_at);

CREATE TABLE IF NOT EXISTS telemetry_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname TEXT, uptime TEXT, cpu_temp REAL,
    backend_ok INTEGER, db_ok INTEGER, api_ok INTEGER,
    recorded_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_telemetry_recorded_at ON telemetry_snapshots(recorded_at);

-- My Garden scan history. One row per analyzed photo (captures row).
-- garden_id stays NULL until the scan is saved to a garden plant; once set,
-- the assessment is kept as history and never replaced. Deleting a garden
-- plant keeps its photos and assessments but unlinks them.
CREATE TABLE IF NOT EXISTS photo_assessments (
    capture_id INTEGER PRIMARY KEY REFERENCES captures(id) ON DELETE CASCADE,
    garden_id INTEGER REFERENCES garden(id) ON DELETE SET NULL,
    assessment_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_photo_assessments_garden ON photo_assessments(garden_id, created_at);
