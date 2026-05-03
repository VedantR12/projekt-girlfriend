from fastapi import FastAPI
from app.routes.persona import router as persona_router
from app.routes.chat import router as chat_router
from app.services.db import supabase 
from app.routes.api_key import router as api_key_router

app = FastAPI(title="Projekt Girlfriend API")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "https://projektgf.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(persona_router)
app.include_router(chat_router)
app.include_router(api_key_router)

@app.get("/")
def home():
    return {"message": "Backend is alive"}  

@app.get("/health")
def health():
    """
    Used by Render to check if service is alive.
    Also pings Supabase to keep it active.
    """
    try:
        # 🔥 lightweight query (fast + cheap)
        res = supabase.table("api_keys").select("id").limit(1).execute()

        return {
            "status": "ok",
            "supabase": "connected" if res.data is not None else "unknown"
        }

    except Exception as e:
        return {
            "status": "error",
            "supabase": str(e)
        }