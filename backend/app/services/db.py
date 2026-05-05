import os
from supabase import create_client, Client
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# Load and validate Supabase configuration
# ----------------------------------------------------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

def _require_env(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(
            f"❌ Supabase configuration error – environment variable '{name}' is missing or empty. "
            "Please set it in your .env file (e.g. SUPABASE_URL=https://<project>.supabase.co)."
        )
    return value

# Validate each variable
_require_env("SUPABASE_URL", SUPABASE_URL)
_require_env("SUPABASE_ANON_KEY", SUPABASE_ANON_KEY)
_require_env("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY)

# ----------------------------------------------------------------------
# Initialise Supabase clients
# ----------------------------------------------------------------------
# ANON client – used for authentication (signup, login, OAuth)
supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# SERVICE client – used for data operations (bypasses RLS). The backend validates the user via JWT.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
