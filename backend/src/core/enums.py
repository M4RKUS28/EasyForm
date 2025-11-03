"""Core enumerations used across the backend."""
from enum import Enum


class AccessLevel(str, Enum):
    """Access level values embedded in JWTs."""

    READ_ONLY = "r"
    WRITE_ONLY = "w"
    READ_WRITE = "rw"

    @property
    def allows_read(self) -> bool:
        return self in {AccessLevel.READ_ONLY, AccessLevel.READ_WRITE}

    @property
    def allows_write(self) -> bool:
        return self in {AccessLevel.WRITE_ONLY, AccessLevel.READ_WRITE}




class UserRole(str, Enum):
    """Enumerated roles available for users."""

    USER = "user"
    PLUS_USER = "plus_user"

    PRO = "pro_user"
    ADMIN = "admin"


class ThemePreference(str, Enum):
    """Available UI theme preferences for users."""

    LIGHT = "light"
    DARK = "dark"


