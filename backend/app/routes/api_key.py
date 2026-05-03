from fastapi import APIRouter, Depends, HTTPException
from app.utils.deps import get_current_user
from app.services.api_key_service import save_api_key, has_api_key, delete_api_key

router = APIRouter(prefix="/api-key", tags=["api-key"])

@router.post("/save")
async def save_key(payload: dict, user_id: str = Depends(get_current_user)):
    key = payload.get("key")
    if not key:
        raise HTTPException(400, "API key required")

    # optional: basic format check
    if not key.startswith("gsk_"):
        raise HTTPException(400, "Invalid Groq key format")

    return save_api_key(user_id, key)


@router.get("/exists")
async def key_exists(user_id: str = Depends(get_current_user)):
    return {"has_key": has_api_key(user_id)}


@router.delete("/delete")
async def delete_key(user_id: str = Depends(get_current_user)):
    return delete_api_key(user_id)