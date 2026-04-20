from fastapi import FastAPI
from app.routes.persona import router as persona_router
from app.routes.chat import router as chat_router

app = FastAPI(title="Projekt Girlfriend API")

app.include_router(persona_router)
app.include_router(chat_router)

@app.get("/")
def home():
    return {"message": "Backend is alive"}