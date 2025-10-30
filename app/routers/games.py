"""FastAPI router for live games and betting insights."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import live_cache
from app.services.live_metrics import build_insight
from app.services.season_profiles import get_season_profiles

router = APIRouter(prefix="/api", tags=["games"])


@router.get("/games/live")
def live_games() -> dict:
    games = live_cache.list_live_games()
    return {"games": games}


@router.get("/games/{game_id}/insight")
def game_insight(game_id: str) -> dict:
    season_profiles = get_season_profiles()
    try:
        insight = build_insight(game_id, season_profiles)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return insight
