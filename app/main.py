from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.database import init_db
from app.gemini_client import procesar_mensaje

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Agentic IA - Asistente Academico")

init_db()

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class Turno(BaseModel):
    role: str
    text: str


class ChatRequest(BaseModel):
    historial: list[Turno] = []
    mensaje: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    historial = [t.model_dump() for t in req.historial]
    return procesar_mensaje(historial, req.mensaje)
