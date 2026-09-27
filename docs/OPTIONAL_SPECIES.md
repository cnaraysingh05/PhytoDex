# Optional species for scanned Garden plants

POST /api/garden accepts an omitted or null plant_id with a nonempty nickname (maximum 60 characters). A supplied plant_id must identify a real PlantDex row. Existing known-species requests remain compatible. The frontend never silently confirms Gemini's guess. An unidentified plant keeps photos, notes and scan history without an invented PlantDex entry; species-specific library fields are null.

Stop the server and run python scripts/init_database.py before restarting. Existing databases receive a timestamped SQLite backup beside the database, then a transactional table migration preserving IDs, records, scan references and indexes. Backups are private and ignored by Git. Repeated initialization does not repeat the migration. Do not delete the database to apply this change.

Manual check: save a scan with a nickname and no species; open it in Garden, refresh and restart the server; verify its photo and history persist. Also save a confirmed species. Unknown plants must not display care instructions for a guessed species.
