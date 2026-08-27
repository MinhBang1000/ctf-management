import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)


class BackupError(Exception):
    pass


def _backup_dir() -> Path:
    path = Path(settings.BACKUP_DIR)
    if not path.is_absolute():
        # Relative to the project root (backend/.. ), not the CWD Celery
        # happens to be started from.
        path = Path(__file__).resolve().parents[3] / settings.BACKUP_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_backup() -> Path:
    """Full-database pg_dump (PRD §7 backup — per-Lab granular backup/
    restore is explicitly out of scope for v1, see OPERATIONS.md for the
    documented manual single-tenant export procedure instead).

    Uses BACKUP_DATABASE_URL — a dedicated, read-only, BYPASSRLS Postgres
    role, NEVER the app's own DATABASE_URL. A pg_dump run by a normal
    (FORCE RLS, non-BYPASSRLS) role gets a filtered or outright failing
    dump; that's a real gotcha found while building this, not a
    hypothetical — see OPERATIONS.md for the full explanation.
    """
    if not settings.BACKUP_DATABASE_URL:
        raise BackupError("BACKUP_DATABASE_URL is not set — see OPERATIONS.md for the one-time role setup.")

    parsed = urlparse(settings.BACKUP_DATABASE_URL)
    dbname = parsed.path.lstrip("/")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = _backup_dir() / f"hslab_ctf_{timestamp}.dump"

    cmd = [
        "pg_dump",
        "-Fc",  # custom format: compressed, restorable with pg_restore
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "hslab_backup",
        "-d", dbname,
        "-f", str(out_file),
    ]
    env = {"PGPASSWORD": parsed.password or ""}

    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise BackupError(f"pg_dump failed (exit {result.returncode}): {result.stderr[:500]}")

    logger.info("Backup written to %s (%d bytes)", out_file, out_file.stat().st_size)
    _apply_retention()
    return out_file


def _apply_retention() -> None:
    backups = sorted(_backup_dir().glob("hslab_ctf_*.dump"), key=lambda p: p.name, reverse=True)
    for stale in backups[settings.BACKUP_RETENTION_COUNT :]:
        stale.unlink(missing_ok=True)
        logger.info("Removed old backup %s (retention=%d)", stale, settings.BACKUP_RETENTION_COUNT)
