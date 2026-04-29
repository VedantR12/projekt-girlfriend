import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

MODE = os.getenv("MODE", "dev")

# DEV MODE: hardcoded test user UUID
DEV_USER_ID = "00000000-0000-0000-0000-000000000001"

# Swagger-friendly auth
security = HTTPBearer(auto_error=MODE != "dev")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    DEV: bypass auth
    PROD: validate token via Supabase
    """

    # ─── DEV BYPASS ───
    if MODE == "dev":
        print(f"⚠️ DEV MODE: auth bypassed → user_id = {DEV_USER_ID}")
        return DEV_USER_ID

    # ─── PROD MODE ───
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )

    token = credentials.credentials

    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": SUPABASE_KEY
    }

    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers=headers
        )

    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user = res.json()

    return user["id"]