"""Email user unik: pesan & deteksi IntegrityError dari unique index. Tanpa DB."""
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppError
from app.services.user_email_rules import email_taken, email_taken_message, is_email_unique_violation


def _ie(constraint=None, text="duplicate key"):
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint))
    orig.__str__ = lambda self=orig: text  # noqa: E731
    return IntegrityError("INSERT", {}, orig)


def test_pesan_409():
    assert email_taken_message("a@teladanprima.com") == "Email a@teladanprima.com sudah dipakai user lain."
    err = email_taken("a@teladanprima.com")
    assert isinstance(err, AppError) and err.status_code == 409
    assert err.detail["errors"][0]["field"] == "email"


def test_deteksi_constraint_email():
    assert is_email_unique_violation(_ie("users_email_lower_key"))
    assert is_email_unique_violation(_ie("users_email_key"))
    assert not is_email_unique_violation(_ie("users_username_key"))


def test_deteksi_dari_teks():
    class Orig(Exception):
        diag = None
    exc = IntegrityError("INSERT", {}, Orig('duplicate key value violates unique constraint "users_email_lower_key"'))
    assert is_email_unique_violation(exc)
    exc2 = IntegrityError("INSERT", {}, Orig('violates unique constraint "users_username_key"'))
    assert not is_email_unique_violation(exc2)
