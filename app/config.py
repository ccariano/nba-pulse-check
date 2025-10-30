"""Application configuration helpers."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class Settings:
    """Container for environment-driven configuration."""

    season: str = os.getenv("SEASON", "2024-25")
    season_type: str = os.getenv("SEASON_TYPE", "Regular Season")
    paid_api_enabled: bool = os.getenv("PAID_API_ENABLED", "false").lower() == "true"
    live_line_source: str = os.getenv("LIVE_LINE_SOURCE", "cache")
    feature_betting_insight: bool = (
        os.getenv("FEATURE_BETTING_INSIGHT", "false").lower() == "true"
    )
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    season_profile_cache: str = os.getenv(
        "SEASON_PROFILE_CACHE", "season_profiles.json"
    )
    live_line_max_calls_month: str | None = os.getenv("LIVE_LINE_MAX_CALLS_MONTH")

    @property
    def season_profile_cache_path(self) -> Path:
        return self.data_dir / self.season_profile_cache


SETTINGS = Settings()


def ensure_data_dir(path: Path | None = None) -> Path:
    """Ensure the data directory exists and return it."""

    base = path or SETTINGS.data_dir
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON data from disk."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    """Persist JSON payload to disk."""

    ensure_data_dir(path.parent)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    tmp_path.replace(path)
