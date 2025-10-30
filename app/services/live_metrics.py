"""Live metrics computation for Betting Insights."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Dict, Optional

from app.services import live_cache
from app.services.season_profiles import SeasonProfileState, TeamSeasonProfile
from app.utils.logger import get_logger

LOGGER = get_logger(__name__)

PACE_MIN = 60.0
PACE_MAX = 120.0
PACE_MIN_ELAPSED_MINUTES = 2.0


@dataclass
class LiveGameContext:
    game_id: str
    live_total: float
    rate_of_change: Optional[str]
    cache_age: Optional[int]
    live_box: Dict[str, object]
    season_profiles: SeasonProfileState

    def get_team_profile(self, team_id: str) -> TeamSeasonProfile:
        try:
            return self.season_profiles.teams[str(team_id)]
        except KeyError as exc:
            raise KeyError(f"Missing season profile for team {team_id}") from exc


class PaceTracker:
    """Maintain last valid pace values per game."""

    def __init__(self) -> None:
        self._latest: Dict[str, float] = {}

    def remember(self, game_id: str, pace: float) -> None:
        self._latest[game_id] = pace

    def last_valid(self, game_id: str) -> Optional[float]:
        return self._latest.get(game_id)


PACE_TRACKER = PaceTracker()


def _parse_clock(clock: str) -> float:
    minutes, seconds = clock.split(":")
    return int(minutes) + int(seconds) / 60.0


def _elapsed_minutes(quarter: int, clock: str) -> float:
    remaining = _parse_clock(clock)
    completed_quarters = max(0, quarter - 1)
    elapsed = completed_quarters * 12 + (12 - remaining)
    return float(elapsed)


def _possessions(team_stats: Dict[str, float]) -> float:
    return (
        float(team_stats.get("fga", 0))
        - float(team_stats.get("oreb", 0))
        + float(team_stats.get("tov", 0))
        + 0.44 * float(team_stats.get("fta", 0))
    )


def _pace(team_a_possessions: float, team_b_possessions: float, minutes_elapsed: float) -> float:
    if minutes_elapsed <= 0:
        return PACE_MIN
    avg_possessions = (team_a_possessions + team_b_possessions) / 2.0
    return 48 * (avg_possessions / minutes_elapsed)


def _pace_delta_pct(live_pace: float, team_a: TeamSeasonProfile, team_b: TeamSeasonProfile) -> float:
    baseline = (team_a.pace + team_b.pace) / 2.0
    if baseline <= 0:
        return 0.0
    return (live_pace - baseline) / baseline


def _expected_points_so_far(minutes_elapsed: float, team_a: TeamSeasonProfile, team_b: TeamSeasonProfile) -> float:
    if minutes_elapsed <= 0:
        return team_a.pts_pg + team_b.pts_pg

    def expected_points(team: TeamSeasonProfile) -> float:
        quarter_shares = [team.q1_share, team.q2_share, team.q3_share, team.q4_share]
        total = 0.0
        minutes_remaining = minutes_elapsed
        for idx, share in enumerate(quarter_shares, start=1):
            quarter_minutes = min(12.0, max(0.0, minutes_remaining))
            minutes_remaining -= 12.0
            fraction = min(1.0, quarter_minutes / 12.0)
            total += team.pts_pg * share * fraction
            if minutes_remaining <= 0:
                break
        return total

    return expected_points(team_a) + expected_points(team_b)


def _alignment(live_total: float, expected_total: float) -> str:
    if expected_total <= 0:
        return "aligned"
    ratio = live_total / expected_total
    if ratio >= 1.03:
        return "above"
    if ratio <= 0.97:
        return "below"
    return "aligned"


def _tempo_summary(pace_delta_pct: float) -> str:
    pct = pace_delta_pct * 100
    if pct >= 20:
        return "Tempo is much faster than normal."
    if 10 <= pct < 20:
        return "Tempo is a bit faster than normal."
    if -20 >= pct:
        return "Tempo is much slower than normal."
    if -20 < pct <= -10:
        return "Tempo is a bit slower than normal."
    return "Tempo is near normal."


def _market_clause(alignment: str) -> str:
    if alignment == "above":
        return "The line looks a little high."
    if alignment == "below":
        return "The line looks a little low."
    return "The line already reflects it."


def _action_hint(alignment: str, pace_delta_pct: float, rate_flag: Optional[str], quarter: int) -> str:
    pct = pace_delta_pct * 100
    if quarter == 4 and rate_flag == "FAST":
        return "Late volatility. Manage risk."
    if alignment == "below" and pct >= 10:
        return "Over could have value."
    if alignment == "above" and pct <= -10:
        return "Under could have value."
    if alignment == "aligned":
        return "No clear edge right now."
    return "Watch for confirmation before acting."


def _volatility_tag(rate_flag: Optional[str]) -> str:
    if rate_flag == "FAST":
        return " Moves are fast. Expect swings."
    return ""


def _defensive_context(team: TeamSeasonProfile) -> Dict[str, object]:
    return {
        "defTeam": team.team_name,
        "psi": team.psi,
        "tempoClampRate": team.tempo_clamp_rate,
        "defDragScore": team.def_drag_score,
    }


def _choose_defensive_anchor(team_a: TeamSeasonProfile, team_b: TeamSeasonProfile, pace_delta_pct: float) -> TeamSeasonProfile:
    if pace_delta_pct >= 0:
        return team_b if team_b.pace < team_a.pace else team_a
    return team_a if team_a.pace < team_b.pace else team_b


def _build_bias(game_id: str, live_total: float, pace_delta_pct: float) -> Dict[str, object]:
    history = live_cache.getLiveLineHistory(game_id)
    if not history:
        return {
            "status": "inactive",
            "direction": None,
            "confidence": 0.0,
            "avgMovement": 0.0,
            "windowMin": 0,
            "sampleSize": 0,
        }

    totals = [float(entry["total"]) for entry in history]
    movements = [abs(b - a) for a, b in zip(totals, totals[1:])]
    avg_movement = sum(movements) / len(movements) if movements else 0.0
    direction = "flat"
    if pace_delta_pct >= 0.05:
        direction = "up"
    elif pace_delta_pct <= -0.05:
        direction = "down"

    sample_size = len(history)
    status = "active" if sample_size >= 3 else "inactive"
    confidence = min(0.95, 0.4 + 0.05 * sample_size) if status == "active" else 0.0

    return {
        "status": status,
        "direction": direction if status == "active" else None,
        "confidence": round(confidence, 2),
        "avgMovement": round(avg_movement, 2),
        "windowMin": 3,
        "sampleSize": sample_size,
    }


def build_insight(game_id: str, season_profiles: SeasonProfileState) -> Dict[str, object]:
    live_total = live_cache.getLiveLine(game_id)
    live_box = live_cache.getLiveBox(game_id)
    rate_flag = live_cache.getRateOfChange(game_id)
    cache_age = live_cache.get_cache_age(game_id)

    if live_total is None or live_box is None:
        raise ValueError(f"Live data unavailable for game {game_id}")

    context = LiveGameContext(
        game_id=game_id,
        live_total=live_total,
        rate_of_change=rate_flag,
        cache_age=cache_age,
        live_box=live_box,
        season_profiles=season_profiles,
    )

    minutes_elapsed = _elapsed_minutes(live_box["quarter"], live_box["clock"])
    pace_valid = minutes_elapsed >= PACE_MIN_ELAPSED_MINUTES

    home_profile = context.get_team_profile(live_box["home"]["teamId"])
    away_profile = context.get_team_profile(live_box["away"]["teamId"])

    home_possessions = _possessions(live_box["home"])
    away_possessions = _possessions(live_box["away"])
    live_pace = _pace(home_possessions, away_possessions, minutes_elapsed)

    if not pace_valid or not (PACE_MIN <= live_pace <= PACE_MAX):
        last = PACE_TRACKER.last_valid(game_id)
        if last is not None:
            live_pace = last
        pace_valid = False
    else:
        PACE_TRACKER.remember(game_id, live_pace)

    pace_delta_pct = _pace_delta_pct(live_pace, home_profile, away_profile)
    expected_so_far = _expected_points_so_far(minutes_elapsed, home_profile, away_profile)
    if minutes_elapsed <= 0:
        expected_total = home_profile.pts_pg + away_profile.pts_pg
    else:
        expected_total = max(1.0, expected_so_far / (minutes_elapsed / 48.0))

    alignment = _alignment(live_total, expected_total)

    defensive_anchor = _choose_defensive_anchor(home_profile, away_profile, pace_delta_pct)
    defense_context = _defensive_context(defensive_anchor)

    summary_parts = [
        _tempo_summary(pace_delta_pct),
        _market_clause(alignment),
        _action_hint(alignment, pace_delta_pct, rate_flag, live_box["quarter"]),
    ]

    if defensive_anchor.psi <= -5 and defensive_anchor.tempo_clamp_rate >= 0.6:
        summary_parts.insert(0, "Defensive clamp likely. Pace may regress.")
    if defensive_anchor.def_drag_score >= 80 and alignment == "above":
        summary_parts[-1] = "Under could have value."
    if defensive_anchor.def_drag_score <= 40 and alignment == "below":
        summary_parts[-1] = "Over could have value."

    summary = " ".join(summary_parts) + _volatility_tag(rate_flag)

    bias = _build_bias(game_id, live_total, pace_delta_pct)

    telemetry = {
        "gameId": game_id,
        "cache_age": cache_age,
        "pace_valid": pace_valid,
        "alignment": alignment,
        "summary_length": len(summary),
    }
    LOGGER.info("insight_render", extra={"telemetry": telemetry})

    return {
        "summary": summary,
        "alignment": alignment,
        "paceDeltaPct": round(pace_delta_pct, 4),
        "defenseContext": defense_context,
        "bias": bias,
        "supporting": {
            "rateOfChange": rate_flag,
            "lineChangeSinceTip": round(live_total - live_cache.getLiveLineHistory(game_id)[0]["total"], 1)
            if live_cache.getLiveLineHistory(game_id)
            else 0.0,
            "liveTotal": live_total,
            "expectedTotalNow": round(expected_total, 1),
            "quarter": live_box["quarter"],
            "timeRemaining": live_box["clock"],
        },
    }
