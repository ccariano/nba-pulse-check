"""FastAPI application entry point."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import ensure_data_dir
from app.routers import games, season_profiles

app = FastAPI(title="NBA Pace Pulse", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_data_dir()

app.include_router(season_profiles.router)
app.include_router(games.router)

app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")


@app.get("/")
def index() -> FileResponse:
    frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
    return FileResponse(frontend_dir / "index.html")
