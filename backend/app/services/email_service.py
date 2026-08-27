import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import settings
from app.models.tenant import Tenant


class EmailConfigError(Exception):
    """Neither the Tenant nor the system has usable SMTP config."""


class EmailSendError(Exception):
    """SMTP connection/auth/send failed."""


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    from_address: str
    use_tls: bool


def get_smtp_config(tenant: Tenant) -> SMTPConfig:
    """Tenant's own SMTP config if set, else the system default from .env
    (PRD §3.4: SMTP is per-Lab with a system fallback)."""
    if tenant.smtp_config:
        cfg = tenant.smtp_config
        return SMTPConfig(
            host=cfg["host"],
            port=int(cfg.get("port", 587)),
            username=cfg.get("username"),
            password=cfg.get("password"),
            from_address=cfg.get("from_address") or cfg.get("username") or "",
            use_tls=bool(cfg.get("use_tls", True)),
        )

    return _system_default_config(f"No SMTP configured for tenant {tenant.id} and ")


def _system_default_config(error_prefix: str = "") -> SMTPConfig:
    if settings.DEFAULT_SMTP_HOST:
        return SMTPConfig(
            host=settings.DEFAULT_SMTP_HOST,
            port=settings.DEFAULT_SMTP_PORT,
            username=settings.DEFAULT_SMTP_USERNAME,
            password=settings.DEFAULT_SMTP_PASSWORD,
            from_address=settings.DEFAULT_SMTP_FROM_ADDRESS or settings.DEFAULT_SMTP_USERNAME or "",
            use_tls=settings.DEFAULT_SMTP_USE_TLS,
        )
    raise EmailConfigError(f"{error_prefix}no system default SMTP is set (DEFAULT_SMTP_HOST).")


def _send_via_smtp(config: SMTPConfig, to_address: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.from_address
    message["To"] = to_address
    message.set_content(body)

    try:
        with smtplib.SMTP(config.host, config.port, timeout=15) as server:
            if config.use_tls:
                server.starttls()
            if config.username and config.password:
                server.login(config.username, config.password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailSendError(f"Failed to send email via {config.host}:{config.port}: {exc}") from exc


def send_email(tenant: Tenant, to_address: str, subject: str, body: str) -> None:
    _send_via_smtp(get_smtp_config(tenant), to_address, subject, body)


def send_test_email(tenant: Tenant, to_address: str) -> None:
    send_email(
        tenant,
        to_address,
        subject="HSLab CTF Classroom — SMTP test",
        body=(
            f"This is a test email from HSLab CTF Classroom for {tenant.name}.\n\n"
            "If you received this, your SMTP configuration is working."
        ),
    )


def send_system_email(to_address: str, subject: str, body: str) -> None:
    """Phase 6 alerting: ALWAYS uses DEFAULT_SMTP_*, never a Tenant's own
    config — an alert about tenant X's job failures shouldn't depend on
    tenant X's own (possibly-broken) SMTP to be delivered. Raises
    EmailConfigError if no system default is set — callers should catch
    and log, not let this crash the job it's alerting about."""
    _send_via_smtp(_system_default_config(), to_address, subject, body)
