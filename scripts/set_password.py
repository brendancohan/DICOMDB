"""CLI utility to update the shared DicomDB account password."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import set_password
from app.config import settings
from app.database import get_connection, init_db


def main() -> None:
    init_db(settings.db_path)
    pw1 = getpass.getpass("New shared password: ")
    pw2 = getpass.getpass("Confirm password: ")
    if not pw1 or pw1 != pw2:
        print("Error: passwords did not match or were empty.")
        sys.exit(1)

    conn = get_connection(settings.db_path)
    try:
        set_password(conn, pw1)
    finally:
        conn.close()
    print(f"Password updated for user '{settings.username}' in {settings.db_path}")


if __name__ == "__main__":
    main()
