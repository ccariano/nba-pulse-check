"""Season profile builder and cache manager."""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

try:  # Optional dependency in tests
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pandas import DataFrame

try:  # Optional dependency in tests
    from nba_api.stats.endpoints import LeagueDashTeamStats
except Exception:  # pragma: no cover - offline fallback
    LeagueDashTeamStats = None  # type: ignore

from app.config import SETTINGS, ensure_data_dir, load_json, save_json
from app.utils.logger import get_logger

LOGGER = get_logger(__name__)


def _prepare_four_factors_frame(frame: "DataFrame") -> "DataFrame":
    """Normalize NBA API four-factors response for downstream merges."""

    # Work on a copy so callers retain their original frame if needed.
    prepared = frame.copy()

    alias_map = {
        "DRB_PCT": ["DREB_PCT", "DEF_REB_PCT"],
        "OPP_FT_RATE": ["OPP_FTA_RATE", "OPP_FT_RATE_ALLOWED"],
    }

    for target, aliases in alias_map.items():
        if target in prepared.columns:
            continue
        replacement = next((alias for alias in aliases if alias in prepared.columns), None)
        if replacement:
            prepared.rename(columns={replacement: target}, inplace=True)

    defaults = {
        "DRB_PCT": 0.0,
        "OPP_FT_RATE": 0.0,
    }

    missing = [column for column in defaults if column not in prepared.columns]
    if missing:
        LOGGER.warning(
            "Four factors data missing columns %s; defaulting to safe values.", missing
        )
        for column in missing:
            prepared[column] = defaults[column]

    return prepared


@dataclass
class TeamSeasonProfile:
    team_id: str
    team_name: str
    pace: float
    pace_rank: int
    pts_pg: float
    q1_share: float
    q2_share: float
    q3_share: float
    q4_share: float
    def_rating: float
    opp_pts_pg: float
    opp_efg_allowed: float
    opp_tov_forced_pct: float
    drb_pct: float
    opp_ft_rate_allowed: float
    opp_fb_pts_allowed: float
    opp_pitp_allowed: float
    opp_2ndch_pts_allowed: float
    psi: float
    tempo_clamp_rate: float
    def_drag_score: float
    transition_kill_rate: float
    late_slow_tendency: float

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "TeamSeasonProfile":
        return cls(
            team_id=str(payload["TEAM_ID"]),
            team_name=str(payload["TEAM_NAME"]),
            pace=float(payload["PACE"]),
            pace_rank=int(payload.get("PACE_RANK", 0)),
            pts_pg=float(payload["PTS_PG"]),
            q1_share=float(payload["Q1_SHARE"]),
            q2_share=float(payload["Q2_SHARE"]),
            q3_share=float(payload["Q3_SHARE"]),
            q4_share=float(payload["Q4_SHARE"]),
            def_rating=float(payload.get("DEF_RATING", 0.0)),
            opp_pts_pg=float(payload.get("OPP_PTS_PG", 0.0)),
            opp_efg_allowed=float(payload.get("OPP_EFG_ALLOWED", 0.0)),
            opp_tov_forced_pct=float(payload.get("OPP_TOV_FORCED_PCT", 0.0)),
            drb_pct=float(payload.get("DRB_PCT", 0.0)),
            opp_ft_rate_allowed=float(payload.get("OPP_FT_RATE_ALLOWED", 0.0)),
            opp_fb_pts_allowed=float(payload.get("OPP_FB_PTS_ALLOWED", 0.0)),
            opp_pitp_allowed=float(payload.get("OPP_PITP_ALLOWED", 0.0)),
            opp_2ndch_pts_allowed=float(payload.get("OPP_2NDCH_PTS_ALLOWED", 0.0)),
            psi=float(payload.get("PSI", 0.0)),
            tempo_clamp_rate=float(payload.get("TEMPO_CLAMP_RATE", 0.0)),
            def_drag_score=float(payload.get("DEF_DRAG_SCORE", 50.0)),
            transition_kill_rate=float(payload.get("TRANSITION_KILL_RATE", 0.0)),
            late_slow_tendency=float(payload.get("LATE_SLOW_TENDENCY", 0.0)),
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "TEAM_ID": self.team_id,
            "TEAM_NAME": self.team_name,
            "PACE": self.pace,
            "PACE_RANK": self.pace_rank,
            "PTS_PG": self.pts_pg,
            "Q1_SHARE": self.q1_share,
            "Q2_SHARE": self.q2_share,
            "Q3_SHARE": self.q3_share,
            "Q4_SHARE": self.q4_share,
            "DEF_RATING": self.def_rating,
            "OPP_PTS_PG": self.opp_pts_pg,
            "OPP_EFG_ALLOWED": self.opp_efg_allowed,
            "OPP_TOV_FORCED_PCT": self.opp_tov_forced_pct,
            "DRB_PCT": self.drb_pct,
            "OPP_FT_RATE_ALLOWED": self.opp_ft_rate_allowed,
            "OPP_FB_PTS_ALLOWED": self.opp_fb_pts_allowed,
            "OPP_PITP_ALLOWED": self.opp_pitp_allowed,
            "OPP_2NDCH_PTS_ALLOWED": self.opp_2ndch_pts_allowed,
            "PSI": self.psi,
            "TEMPO_CLAMP_RATE": self.tempo_clamp_rate,
            "DEF_DRAG_SCORE": self.def_drag_score,
            "TRANSITION_KILL_RATE": self.transition_kill_rate,
            "LATE_SLOW_TENDENCY": self.late_slow_tendency,
        }


@dataclass
class SeasonProfileState:
    refreshed: dt.datetime
    teams: Dict[str, TeamSeasonProfile] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Dict[str, object]) -> "SeasonProfileState":
        refreshed = dt.datetime.fromisoformat(str(payload.get("refreshed")))
        teams = {
            entry["TEAM_ID"]: TeamSeasonProfile.from_dict(entry)
            for entry in payload.get("teams", [])
        }
        return cls(refreshed=refreshed, teams=teams)

    def to_payload(self) -> Dict[str, object]:
        return {
            "refreshed": self.refreshed.isoformat(),
            "teams": [profile.to_dict() for profile in self.teams.values()],
        }


class SeasonProfileService:
    """Manage season profile lifecycle and caching."""

    def __init__(self, cache_path: Optional[Path] = None) -> None:
        self.cache_path = cache_path or SETTINGS.season_profile_cache_path
        ensure_data_dir(self.cache_path.parent)
        self._state: Optional[SeasonProfileState] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_profiles(self, force_refresh: bool = False) -> SeasonProfileState:
        if not force_refresh:
            state = self._state or self._load_from_cache()
            if state and self._is_fresh(state.refreshed):
                return state

        LOGGER.info("Refreshing season profiles from source")
        state = self._refresh_from_source()
        self._state = state
        save_json(self.cache_path, state.to_payload())
        return state

    # ------------------------------------------------------------------
    def _load_from_cache(self) -> Optional[SeasonProfileState]:
        if not self.cache_path.exists():
            return None
        try:
            payload = load_json(self.cache_path)
            return SeasonProfileState.from_payload(payload)
        except Exception as exc:  # pragma: no cover - corrupted cache
            LOGGER.warning("Failed to load cached season profiles: %s", exc)
            return None

    def _is_fresh(self, refreshed: dt.datetime) -> bool:
        return (dt.datetime.utcnow() - refreshed) <= dt.timedelta(hours=24)

    # ------------------------------------------------------------------
    def _refresh_from_source(self) -> SeasonProfileState:
        if LeagueDashTeamStats is None:
            LOGGER.warning("nba_api not available; falling back to bundled sample data")
            payload = load_json(Path("data/sample_season_profiles.json"))
            return SeasonProfileState.from_payload(payload)

        try:
            teams = self._build_profiles_from_api()
        except Exception as exc:  # pragma: no cover - network failure
            LOGGER.error("Failed to refresh season profiles from NBA API: %s", exc)
            payload = load_json(Path("data/sample_season_profiles.json"))
            return SeasonProfileState.from_payload(payload)

        refreshed = dt.datetime.utcnow()
        return SeasonProfileState(refreshed=refreshed, teams=teams)

    # ------------------------------------------------------------------
    def _build_profiles_from_api(self) -> Dict[str, TeamSeasonProfile]:  # pragma: no cover - requires network
        season = SETTINGS.season
        season_type = SETTINGS.season_type

        base = LeagueDashTeamStats(
            measure_type_detailed_defense="Base",
            season=season,
            per_mode_detailed="PerGame",
            season_type_all_star=season_type,
        ).get_data_frames()[0]
        advanced = LeagueDashTeamStats(
            measure_type_detailed_defense="Advanced",
            season=season,
            per_mode_detailed="PerGame",
            season_type_all_star=season_type,
        ).get_data_frames()[0]
        four_factors = LeagueDashTeamStats(
            measure_type_detailed_defense="Four Factors",
            season=season,
            per_mode_detailed="PerGame",
            season_type_all_star=season_type,
        ).get_data_frames()[0]

        four_factors = _prepare_four_factors_frame(four_factors)

        merged = base.merge(
            advanced[["TEAM_ID", "PACE", "PACE_RANK", "DEF_RATING"]],
            on="TEAM_ID",
        ).merge(
            four_factors[
                [
                    "TEAM_ID",
                    "OPP_EFG_PCT",
                    "OPP_TOV_PCT",
                    "DRB_PCT",
                    "OPP_FT_RATE",
                ]
            ],
            on="TEAM_ID",
        )

        merged.rename(
            columns={
                "TEAM_NAME": "TEAM_NAME",
                "PACE": "PACE",
                "PACE_RANK": "PACE_RANK",
                "DEF_RATING": "DEF_RATING",
                "OPP_EFG_PCT": "OPP_EFG_ALLOWED",
                "OPP_TOV_PCT": "OPP_TOV_FORCED_PCT",
                "OPP_FT_RATE": "OPP_FT_RATE_ALLOWED",
            },
            inplace=True,
        )

        merged["PTS_PG"] = merged[["PTS_QTR1", "PTS_QTR2", "PTS_QTR3", "PTS_QTR4"]].sum(axis=1)
        for idx, quarter in enumerate(["Q1", "Q2", "Q3", "Q4"], start=1):
            merged[f"{quarter}_SHARE"] = (
                merged[f"PTS_QTR{idx}"] / merged["PTS_PG"]
            ).fillna(0)

        # Derived defensive metrics placeholders
        if pd is None:
            raise RuntimeError("pandas required for live API refresh")

        merged["OPP_PTS_PG"] = merged.get("OPP_PTS", pd.Series([0] * len(merged)))
        merged["OPP_FB_PTS_ALLOWED"] = 0
        merged["OPP_PITP_ALLOWED"] = 0
        merged["OPP_2NDCH_PTS_ALLOWED"] = 0
        merged["PSI"] = -5
        merged["TEMPO_CLAMP_RATE"] = 0.55
        merged["DEF_DRAG_SCORE"] = (
            100
            - 100
            * (
                merged["OPP_EFG_ALLOWED"].rank(pct=True)
                + merged["DRB_PCT"].rank(pct=True)
                + merged["OPP_FT_RATE_ALLOWED"].rank(pct=True)
            )
            / 3
        )
        merged["TRANSITION_KILL_RATE"] = 0.5
        merged["LATE_SLOW_TENDENCY"] = 0.4

        teams: Dict[str, TeamSeasonProfile] = {}
        for row in merged.to_dict(orient="records"):
            teams[str(row["TEAM_ID"])] = TeamSeasonProfile.from_dict(row)
        return teams


service = SeasonProfileService()


def get_season_profiles(force_refresh: bool = False) -> SeasonProfileState:
    return service.get_profiles(force_refresh=force_refresh)
