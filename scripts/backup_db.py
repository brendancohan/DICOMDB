"""Pure-Python WAL-safe SQLite backup script (no PowerShell required)."""
import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a WAL-safe DicomDB SQLite backup.")
    parser.add_argument("--db", default=settings.db_path, help="Path to source SQLite database")
    parser.add_argument("--backup-dir", default="backups", help="Directory to store backups")
    parser.add_argument("--keep-days", type=int, default=30, help="Delete backups older than N days")
    args = parser.parse_args()

    src_path = Path(args.db)
    if not src_path.is_file():
        print(f"Error: database not found at {src_path}", file=sys.stderr)
        sys.exit(1)

    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = backup_dir / f"pacs_inventory_{stamp}.db"

    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(dest_path))
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()

    print(f"Backed up database to {dest_path}")

    cutoff = time.time() - (args.keep_days * 86400)
    for old_file in backup_dir.glob("pacs_inventory_*.db"):
        if old_file.stat().st_mtime < cutoff:
            old_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
