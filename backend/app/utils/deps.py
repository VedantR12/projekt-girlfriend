import os
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
MODE = os.getenv("MODE", "dev")

# DEV MODE: hardcoded test user UUID
DEV_USER_ID = "00000000-0000-0000-0000-000000000001"

# In dev mode, make the Bearer token optional so Swagger works without auth
security = HTTPBearer(auto_error=MODE != "dev")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Verify Supabase JWT and return user_id (uuid string).

    In MODE=dev: skips JWT check entirely, returns DEV_USER_ID.
    In MODE=prod: requires valid Bearer token, raises 401 otherwise.
    """

    # ─── DEV BYPASS ───
    if MODE == "dev":
        print(f"⚠️  DEV MODE: auth bypassed → user_id = {DEV_USER_ID}")
        return DEV_USER_ID

    # ─── PROD: enforce JWT ───
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required in production mode."
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no user ID found"
            )

        return user_id

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )