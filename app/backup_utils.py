import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.auth import ensure_default_password
from app.database import get_connection, init_db

SQLITE_MAGIC = b"SQLite format 3\x00"
REQUIRED_TABLES = {
    "settings",
    "modalities",
    "modality_ae_titles",
    "destinations",
    "modality_routes",
    "field_definitions",
    "audit_log",
}


def create_backup_bytes(db_path: str) -> bytes:
    """Create a consistent SQLite backup using the online backup API and return its bytes."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        src = get_connection(db_path)
        dst = sqlite3.connect(str(tmp_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def validate_backup_file(path: Path) -> None:
    """Validate that path is a healthy SQLite database containing all DicomDB tables."""
    if not path.is_file() or path.stat().st_size < len(SQLITE_MAGIC):
        raise ValueError("Uploaded file is empty or too small to be a SQLite database.")

    with path.open("rb") as f:
        header = f.read(len(SQLITE_MAGIC))
    if header != SQLITE_MAGIC:
        raise ValueError("Uploaded file is not a valid SQLite database.")

    conn = sqlite3.connect(str(path))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise ValueError("Database failed SQLite integrity check.")

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise ValueError(
                f"Database is missing required DicomDB tables: {', '.join(missing)}"
            )
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Invalid SQLite database: {exc}") from exc
    finally:
        conn.close()


def restore_database_from_bytes(db_path: str, file_bytes: bytes) -> str:
    """Validate uploaded DB, save a pre-restore safety snapshot, and restore in-place."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        validate_backup_file(tmp_path)

        db_file = Path(db_path)
        safety_dir = db_file.parent / "pre_restore_backups"
        safety_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safety_name = f"pre_restore_{stamp}.db"
        safety_path = safety_dir / safety_name

        # Save automatic pre-restore safety backup of current live DB
        live_conn = get_connection(db_path)
        safety_conn = sqlite3.connect(str(safety_path))
        try:
            live_conn.backup(safety_conn)
        finally:
            safety_conn.close()
            live_conn.close()

        # Restore uploaded DB into live DB using online backup API (WAL/Windows safe)
        src_conn = sqlite3.connect(str(tmp_path))
        dst_conn = get_connection(db_path)
        try:
            src_conn.backup(dst_conn)
            dst_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            src_conn.close()
            dst_conn.close()

        # Ensure schema & default password integrity
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            ensure_default_password(conn)
        finally:
            conn.close()

        return safety_name
    finally:
        tmp_path.unlink(missing_ok=True)


def list_safety_backups(db_path: str) -> list[dict[str, Any]]:
    """List pre-restore safety backups sorted newest first."""
    safety_dir = Path(db_path).parent / "pre_restore_backups"
    if not safety_dir.is_dir():
        return []

    items: list[dict[str, Any]] = []
    for p in sorted(safety_dir.glob("pre_restore_*.db"), reverse=True):
        stat = p.stat()
        items.append(
            {
                "name": p.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                ),
            }
        )
    return items
