import base64
import hashlib
import hmac
import os

try:
    from passlib.context import CryptContext
except Exception:  # noqa: BLE001
    CryptContext = None


def _hash_scrypt(password: str) -> str:
    salt = os.urandom(16)
    n, r, p = 2**14, 8, 1
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
    return "scrypt$16384$8$1${}${}".format(
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(key).decode("ascii"),
    )


def _verify_scrypt(password: str, stored_hash: str) -> bool:
    try:
        _, n, r, p, salt_b64, key_b64 = stored_hash.split("$")
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected_key = base64.urlsafe_b64decode(key_b64.encode("ascii"))
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_key),
        )
        return hmac.compare_digest(derived, expected_key)
    except Exception:  # noqa: BLE001
        return False


def hash_password(password: str) -> str:
    return _hash_scrypt(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    if password_hash.startswith("scrypt$"):
        return _verify_scrypt(plain_password, password_hash)

    # Legacy fallback for existing bcrypt hashes.
    if password_hash.startswith("$2") and CryptContext is not None:
        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return ctx.verify(plain_password, password_hash)

    return False
