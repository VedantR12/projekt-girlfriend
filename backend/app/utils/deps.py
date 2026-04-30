import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from app.services.db import supabase

load_dotenv()

MODE = os.getenv("MODE", "dev")

# DEV MODE: hardcoded test user UUID
DEV_USER_ID = "00000000-0000-0000-0000-000000000001"

# In dev mode, make the Bearer token optional so Swagger works without auth
security = HTTPBearer(auto_error=MODE != "dev")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:

    if MODE == "dev":
        return DEV_USER_ID

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization required"
        )

    token = credentials.credentials

    try:
        # 🔥 Use Supabase to verify token
        response = supabase.auth.get_user(token)

        if not response or not response.user:
            raise HTTPException(401, "Invalid token")

        return response.user.id

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )