"""Serialize company calendar publication and deadline commitments consistently."""

import hashlib

from sqlalchemy import text


def lock_company(session, issuer):
    if session.get_bind().dialect.name == "postgresql":
        key = int.from_bytes(
            hashlib.sha256(("calendar:" + issuer).encode()).digest()[:8], signed=True
        )
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
