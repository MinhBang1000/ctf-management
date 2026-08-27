from pydantic import BaseModel, EmailStr


class SMTPConfigOut(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    from_address: str | None = None
    use_tls: bool | None = None
    has_credentials: bool


class SMTPConfigUpdate(BaseModel):
    host: str
    port: int = 587
    username: str | None = None
    password: str
    from_address: str | None = None
    use_tls: bool = True


class ProfessorEmailUpdate(BaseModel):
    professor_email: EmailStr | None = None


class TenantSettingsOut(BaseModel):
    smtp: SMTPConfigOut
    professor_email: str | None


class SendTestEmailRequest(BaseModel):
    to_address: EmailStr
