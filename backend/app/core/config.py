from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000

    DATABASE_URL: str = "postgresql://hslab:hslab@localhost:5432/hslab_ctf"

    JWT_SECRET_KEY: str = "change-me-in-env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    CORS_ORIGINS: str = "http://localhost:3000"
    # §2 forgot-password: base URL used to build the reset link in the
    # email (e.g. "{PUBLIC_APP_URL}/reset-password?token=..."). Kept
    # separate from CORS_ORIGINS (an allow-list, not necessarily ordered
    # or singular) even though they hold the same value in this project's
    # single-frontend deployment.
    PUBLIC_APP_URL: str = "http://localhost:3000"

    # §2 — how long a forgot-password reset link/token stays valid.
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    SUPER_ADMIN_BOOTSTRAP_EMAIL: str | None = None
    SUPER_ADMIN_BOOTSTRAP_PASSWORD: str | None = None

    CLOUDFLARE_TUNNEL_TOKEN: str | None = None

    PLATFORM_SECRET_KEY: str = "unset-generate-a-real-fernet-key"

    REDIS_URL: str = "redis://localhost:6379/0"

    # Root Me publishes no documented rate limit (PRD §4.2 only confirms
    # 429s are possible, IP-based not api_key-based) — these are a
    # conservative starting guess, tune from observed 429 behavior.
    ROOTME_RATE_LIMIT_CAPACITY: float = 5
    ROOTME_RATE_LIMIT_REFILL_PER_SECOND: float = 1.0
    RATE_LIMIT_ACQUIRE_TIMEOUT_SECONDS: float = 30

    # Scheduled sync frequency — a config value, not hardcoded, per PRD
    # §4.2.1 step 2 (exact Root Me timestamps mean frequency only affects
    # detection speed, not accuracy). Default: once a day.
    SYNC_INTERVAL_MINUTES: int = 1440

    # Superseded by per-Lab TenantAutomationSettings + app.tasks.
    # automation_dispatcher — reminders and the weekly report used to run
    # on one system-wide schedule read from these three values; now every
    # Lab has its own schedule in the DB, editable from Settings. Left
    # here (unused) rather than deleted since existing .env files still
    # define them and removing outright isn't necessary.
    REMINDER_CHECK_HOUR_UTC: int = 6
    WEEKLY_REPORT_DAY_OF_WEEK: int = 1
    WEEKLY_REPORT_HOUR_UTC: int = 0

    # How often app.tasks.automation_dispatcher.dispatch_automation checks
    # every active Tenant's own schedule. Short enough that a schedule
    # fires within a few minutes of its target time, long enough not to
    # hammer the DB — this is a coarse polling tick, not itself a schedule.
    AUTOMATION_DISPATCH_INTERVAL_SECONDS: int = 300

    # System-default SMTP, used when a Tenant hasn't configured its own
    # (PRD §3.4: "fallback SMTP mặc định của hệ thống nếu Lab chưa cấu hình").
    DEFAULT_SMTP_HOST: str | None = None
    DEFAULT_SMTP_PORT: int = 587
    DEFAULT_SMTP_USERNAME: str | None = None
    DEFAULT_SMTP_PASSWORD: str | None = None
    DEFAULT_SMTP_FROM_ADDRESS: str | None = None
    DEFAULT_SMTP_USE_TLS: bool = True

    # Dedicated, read-only, BYPASSRLS role used ONLY for pg_dump backups —
    # never the app's own runtime connection (see OPERATIONS.md for why:
    # a FORCE-RLS, non-BYPASSRLS role gets a filtered/failing pg_dump).
    BACKUP_DATABASE_URL: str | None = None
    BACKUP_DIR: str = "./backups"
    BACKUP_RETENTION_COUNT: int = 14
    BACKUP_HOUR_UTC: int = 3

    # Consecutive job failures (sync/reminder/weekly_report) for one
    # Tenant before Super Admin gets an actual email alert. Fires once
    # per failure streak (checked with ==, not >=).
    ALERT_FAILURE_THRESHOLD: int = 3

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
