import os
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from app.services.db import supabase
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────
# API Key Encryption Service
# Uses Fernet symmetric encryption
# ──────────────────────────────────────────

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

_fernet = None


def _get_fernet():
    """Lazy-init Fernet cipher."""
    global _fernet
    if _fernet is None:
        if not ENCRYPTION_KEY:
            raise ValueError(
                "ENCRYPTION_KEY not set in .env. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(ENCRYPTION_KEY.encode())
    return _fernet


def encrypt_key(raw_key: str) -> str:
    """Encrypt a raw API key string."""
    f = _get_fernet()
    print("encrypt key:", ENCRYPTION_KEY)
    return f.encrypt(raw_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    """Decrypt an encrypted API key string."""
    f = _get_fernet()
    print("decrypt key:", ENCRYPTION_KEY)
    return f.decrypt(encrypted_key.encode()).decode()


def save_api_key(user_id: str, raw_key: str):
    """
    Encrypt and store user's Groq API key.
    Upserts — if key exists, updates it.
    """
    encrypted = encrypt_key(raw_key)

    # Check if key already exists
    existing = supabase.table("api_keys") \
        .select("id") \
        .eq("user_id", user_id) \
        .execute()

    if existing.data:
        # Update existing
        supabase.table("api_keys") \
            .update({
                "encrypted_key": encrypted,
                "updated_at": "now()"
            }) \
            .eq("user_id", user_id) \
            .execute()
    else:
        # Insert new
        supabase.table("api_keys") \
            .insert({
                "user_id": user_id,
                "encrypted_key": encrypted
            }) \
            .execute()

    return {"status": "saved"}


def get_api_key(user_id: str) -> str | None:
    result = supabase.table("api_keys") \
        .select("encrypted_key") \
        .eq("user_id", user_id) \
        .execute()

    if not result.data:
        return None

    encrypted = result.data[0]["encrypted_key"]

    try:
        return decrypt_key(encrypted)

    except InvalidToken:
        print("❌ Invalid encryption token — clearing stored key")

        # delete broken key from DB
        supabase.table("api_keys") \
            .delete() \
            .eq("user_id", user_id) \
            .execute()

        return None

def has_api_key(user_id: str) -> bool:
    """Check if user has a stored API key."""
    result = supabase.table("api_keys") \
        .select("id") \
        .eq("user_id", user_id) \
        .execute()

    return bool(result.data)


def delete_api_key(user_id: str):
    """Delete user's stored API key."""
    supabase.table("api_keys") \
        .delete() \
        .eq("user_id", user_id) \
        .execute()

    return {"status": "deleted"}
