"""Local adapter around the paid live line cache.

This module intentionally provides a lightweight abstraction with the exact
interfaces outlined in the project brief. In production the functions should
bind to the real cache implementation. For local development and automated
tests we hydrate them from JSON snapshots under ``data``.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.logger import get_logger

LOGGER = get_logger(__name__)

_DATA_PATH = Path("data/live_snapshots.json")


def _load_snapshots() -> Dict[str, Any]:
    if not _DATA_PATH.exists():
        LOGGER.warning("Live snapshot cache missing at %s", _DATA_PATH)
        return {"games": []}
    with _DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _find_game(game_id: str) -> Dict[str, Any] | None:
    payload = _load_snapshots()
    for game in payload.get("games", []):
        if str(game.get("gameId")) == str(game_id):
            return game
    return None


def getLiveLine(game_id: str) -> Optional[float]:  # noqa: N802 - public contract
    game = _find_game(game_id)
    if game:
        return float(game.get("liveTotal"))
    return None


def getLiveLineHistory(game_id: str) -> List[Dict[str, Any]]:  # noqa: N802
    game = _find_game(game_id)
    if not game:
        return []
    return game.get("lineHistory", [])


def getRateOfChange(game_id: str) -> Optional[str]:  # noqa: N802
    game = _find_game(game_id)
    if not game:
        return None
    return game.get("rateOfChange")


def getLiveBox(game_id: str) -> Optional[Dict[str, Any]]:  # noqa: N802
    game = _find_game(game_id)
    if not game:
        return None
    return game.get("liveBox")


def list_live_games() -> List[Dict[str, Any]]:
    payload = _load_snapshots()
    return payload.get("games", [])


def get_cache_age(game_id: str) -> Optional[int]:
    game = _find_game(game_id)
    if not game:
        return None
    updated = game.get("updated")
    if not updated:
        return None
    timestamp = dt.datetime.fromisoformat(updated)
    return int((dt.datetime.utcnow() - timestamp).total_seconds())
