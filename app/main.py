from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import ensure_default_password
from app.config import settings
from app.database import get_connection, init_db
from app.deps import RedirectToLogin
from app.routes import (
    audit_routes,
    auth_routes,
    conflict_routes,
    destination_routes,
    export_routes,
    field_routes,
    import_routes,
    modality_routes,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(settings.db_path)
    conn = get_connection(settings.db_path)
    try:
        ensure_default_password(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="DicomDB", lifespan=lifespan)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.exception_handler(RedirectToLogin)
def _redirect_to_login(_: Request, __: RedirectToLogin) -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


app.include_router(auth_routes.router)
app.include_router(modality_routes.router)
app.include_router(field_routes.router)
app.include_router(destination_routes.router)
app.include_router(conflict_routes.router)
app.include_router(audit_routes.router)
app.include_router(import_routes.router)
app.include_router(export_routes.router)
