from fastapi import FastAPI
from app.routes.persona import router as persona_router
from app.routes.chat import router as chat_router
from app.services.db import supabase 
from app.routes.api_key import router as api_key_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Projekt Girlfriend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://projektgf.netlify.app",
        "http://localhost:5500",
        "http://127.0.0.1:5500"],
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
    return {"status": "ok"}

@app.get("/keepalive")
def keepalive():

    response = {
        "server": "alive",
        "database": "unknown"
    }

    try:
        res = supabase.table("api_keys").select("id").limit(1).execute()

        response["database"] = (
            "connected" if res.data is not None else "unknown"
        )

    except Exception as e:
        print("Keepalive error:", e)
        response["database"] = "disconnected"

    return response