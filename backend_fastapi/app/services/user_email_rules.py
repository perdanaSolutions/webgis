"""Aturan email user: unik (case-insensitive). Dipakai create & update user."""
from app.core.exceptions import AppError, conflict

# Unique index di auth.users: users_email_key (email) dan users_email_lower_key (lower(email), migrasi 020).
EMAIL_UNIQUE_CONSTRAINTS = ("users_email_key", "users_email_lower_key")


def email_taken_message(email: str) -> str:
    return f"Email {email} sudah dipakai user lain."


def email_taken(email: str) -> AppError:
    return conflict(email_taken_message(email), field="email")


def is_email_unique_violation(exc: BaseException) -> bool:
    """True bila IntegrityError berasal dari unique index email (race dua request bersamaan)."""
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    name = getattr(diag, "constraint_name", None) or ""
    if name in EMAIL_UNIQUE_CONSTRAINTS:
        return True
    text = str(orig or exc)
    return any(c in text for c in EMAIL_UNIQUE_CONSTRAINTS)
