from fastapi import FastAPI
from app.routes.persona import router as persona_router

app = FastAPI()

app.include_router(persona_router)

@app.get("/")
def home():
    return {"message": "Backend is alive"}