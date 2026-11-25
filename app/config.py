import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(env_path: Path) -> None:
    """Load key=value pairs from a .env file into os.environ if not already set."""
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_BASE_DIR = Path(__file__).resolve().parent.parent
_load_dotenv(_BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("DICOMDB_HOST", "0.0.0.0")
    port: int = int(os.getenv("DICOMDB_PORT", "8000"))
    db_path: str = os.getenv("DICOMDB_DB_PATH", str(_BASE_DIR / "data" / "pacs_inventory.db"))
    secret_key: str = os.getenv("DICOMDB_SECRET_KEY", "change-me-in-production")
    username: str = os.getenv("DICOMDB_USERNAME", "pacsadmin")
    default_password: str = os.getenv("DICOMDB_DEFAULT_PASSWORD", "changeme")
    calling_aet: str = os.getenv("DICOMDB_CALLING_AET", "DICOMDB")


settings = Settings()
