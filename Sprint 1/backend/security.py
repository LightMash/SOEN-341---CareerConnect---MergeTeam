import datetime  # for setting token expiration times
import os  # for reading the SECRET_KEY from environment variables

import bcrypt  # handles password hashing/verification directly (no passlib middleman)
from jose import jwt, JWTError  # jwt: create/decode JSON Web Tokens; JWTError: the exception it raises

# The secret key used to sign JWTs (JSON Web Tokens). Anyone with this key could
# forge valid login tokens, so in real deployment it must come from an
# environment variable, never be hardcoded or committed to Git.
# The "dev-secret-change-me" fallback only exists so the app doesn't crash if
# SECRET_KEY is missing locally — it should never be relied on for anything real.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"  # the hashing algorithm used to sign/verify the JWT
ACCESS_TOKEN_EXPIRE_HOURS = 24  # how long a login token stays valid before expiring

def hash_password(password: str) -> str:
    """Turn a plain-text password into a one-way bcrypt hash for storage.
    We NEVER store the plain password itself.
    bcrypt works on bytes, not str, so we encode/decode UTF-8 manually here."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plain-text password (from a login attempt) against the stored
    hash, without ever needing to reverse the hash back into plain text."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    """Build a signed JWT for a given user, used as their login session token."""
    payload = {
        "user_id": user_id,  # embed which user this token belongs to
        # token expires 24 hours from now (UTC, to avoid timezone bugs)
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    # jwt.encode signs the payload with SECRET_KEY, producing a tamper-proof string.
    # Anyone can read the payload, but only someone with SECRET_KEY can have created
    # a token that verifies successfully — that's what makes it trustworthy.
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    """Verify a token's signature and expiration, and return its payload if valid."""
    try:
        # jwt.decode both verifies the signature (using SECRET_KEY) AND checks
        # that "exp" hasn't passed. Raises JWTError if either check fails.
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        # Invalid signature, tampered token, or expired — treat all the same:
        # return None so the caller can respond with "unauthorized".
        return None
