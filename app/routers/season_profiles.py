"""FastAPI router for season profiles."""
from __future__ import annotations

from fastapi import APIRouter

from app.services.season_profiles import get_season_profiles

router = APIRouter(prefix="/api", tags=["season-profiles"])


@router.get("/seasonProfiles")
def season_profiles() -> dict:
    state = get_season_profiles()
    return state.to_payload()
