import sqlite3
from pathlib import Path
from typing import Generator

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.auth import get_current_user
from app.config import settings
from app.database import get_connection
from app.dicom_utils import find_conflicts

BASE_APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_APP_DIR / "templates"))


class RedirectToLogin(Exception):
    pass


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def require_user(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=401, detail="Authentication required")
        raise RedirectToLogin()
    return user


def base_context(
    request: Request,
    conn: sqlite3.Connection,
    active_nav: str = "inventory",
    **extra: object,
) -> dict:
    conflicts = find_conflicts(conn)
    return {
        "request": request,
        "active_nav": active_nav,
        "conflict_count": conflicts["total_count"],
        "username": get_current_user(request) or settings.username,
        **extra,
    }
