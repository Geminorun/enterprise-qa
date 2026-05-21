from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3


def initialize_database(
    db_path: Path,
    schema_path: Path,
    seed_path: Path,
    *,
    overwrite: bool = False,
) -> None:
    if db_path.exists():
        if not overwrite:
            raise FileExistsError(f"database already exists: {db_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")
    seed_sql = seed_path.read_text(encoding="utf-8")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_suffix(db_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(tmp_path)
        conn.executescript(schema_sql)
        conn.executescript(seed_sql)
        conn.commit()
    except Exception:
        if conn is not None:
            conn.close()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    else:
        conn.close()

    try:
        tmp_path.replace(db_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize enterprise QA SQLite database.")
    parser.add_argument("--db", default="data/enterprise.db")
    parser.add_argument("--schema", default="data/schema.sql")
    parser.add_argument("--seed", default="data/seed_data.sql")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    initialize_database(
        Path(args.db),
        Path(args.schema),
        Path(args.seed),
        overwrite=args.overwrite,
    )
    print(f"数据库初始化完成：{args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
