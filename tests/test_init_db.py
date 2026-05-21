import sqlite3
from pathlib import Path

import pytest

from scripts.init_db import initialize_database


def test_initialize_database_creates_expected_tables(tmp_path):
    db_path = tmp_path / "enterprise.db"
    schema_path = Path("data/schema.sql")
    seed_path = Path("data/seed_data.sql")

    initialize_database(db_path, schema_path, seed_path, overwrite=True)

    with sqlite3.connect(db_path) as conn:
        employees = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        members = conn.execute("SELECT COUNT(*) FROM project_members").fetchone()[0]
        attendance = conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
        reviews = conn.execute("SELECT COUNT(*) FROM performance_reviews").fetchone()[0]

    assert employees == 10
    assert projects == 5
    assert members == 12
    assert attendance == 40
    assert reviews == 17


def test_initialize_database_refuses_existing_database_without_overwrite(tmp_path):
    db_path = tmp_path / "enterprise.db"
    tmp_path_db = db_path.with_suffix(db_path.suffix + ".tmp")
    schema_path = Path("data/schema.sql")
    seed_path = Path("data/seed_data.sql")
    db_path.write_bytes(b"original database")

    with pytest.raises(FileExistsError):
        initialize_database(db_path, schema_path, seed_path, overwrite=False)

    assert db_path.read_bytes() == b"original database"
    assert not tmp_path_db.exists()


def test_initialize_database_preserves_existing_database_when_seed_fails(tmp_path):
    db_path = tmp_path / "enterprise.db"
    schema_path = tmp_path / "schema.sql"
    seed_path = tmp_path / "seed.sql"
    tmp_path_db = db_path.with_suffix(db_path.suffix + ".tmp")
    schema_path.write_text(
        "CREATE TABLE new_table (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    seed_path.write_text(
        "INSERT INTO missing_table VALUES (1);",
        encoding="utf-8",
    )

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE preserved (value TEXT NOT NULL)")
        conn.execute("INSERT INTO preserved VALUES ('original')")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(sqlite3.DatabaseError):
        initialize_database(db_path, schema_path, seed_path, overwrite=True)

    with sqlite3.connect(db_path) as conn:
        values = conn.execute("SELECT value FROM preserved").fetchall()

    assert values == [("original",)]
    assert not tmp_path_db.exists()
