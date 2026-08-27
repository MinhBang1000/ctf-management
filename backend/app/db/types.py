import json

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.PLATFORM_SECRET_KEY.encode())


class EncryptedJSON(TypeDecorator):
    """A JSON-serializable dict, encrypted at rest with Fernet.

    Used for Platform.auth_config (e.g. the Root Me api_key) so credentials
    are never stored in plaintext. Decryption only happens when the ORM
    loads the column in Python — nothing is ever exposed through this at
    the SQL level, and API response schemas never include this field.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet().encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return json.loads(_fernet().decrypt(value.encode()))
        except InvalidToken:
            # PLATFORM_SECRET_KEY was rotated/lost since this was written.
            return None
