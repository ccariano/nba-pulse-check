# NBA Pace Pulse

NBA Pace Pulse is a FastAPI + vanilla JavaScript application that surfaces a
single betting insight card for each live NBA game. The platform fuses season
baselines from the NBA Stats API with live game state sourced from a cached
paid feed. It highlights whether tempo spikes or dips are likely to revert and
how the current market total aligns with expectations.

## Features

- Daily season profile builder with disk + memory caching
- Live pace, expected total, and defensive context engine
- Bias detection from intra-game line history
- FastAPI backend with `/api/seasonProfiles`, `/api/games/live`, and
  `/api/games/<id>/insight`
- Minimalist control-panel inspired UI that refreshes insights every 12 seconds

## Getting Started

### Prerequisites

- Python 3.11
- Node.js is **not** required; the front-end is plain HTML/CSS/JS.

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables

```
SEASON=2025-26
SEASON_TYPE="Regular Season"
PAID_API_ENABLED=true
LIVE_LINE_SOURCE=cache
FEATURE_BETTING_INSIGHT=true
```

All variables default to sensible values for development. Set
`FEATURE_BETTING_INSIGHT=false` to disable enhanced logging.

### Running the App

```bash
uvicorn app.main:app --reload --port 8000
```

Then open [http://localhost:8000/frontend](http://localhost:8000/frontend) to
use the interface.

### Season Profiles

The `SeasonProfileService` uses `nba_api.stats.endpoints.LeagueDashTeamStats`
to assemble per-team baselines covering pace, scoring, and defensive
suppression metrics. Profiles are cached to `data/season_profiles.json` and
refreshed when older than 24 hours. For offline development the service falls
back to `data/sample_season_profiles.json`.

### Live Data Cache

All live game data is read from JSON snapshots via the cache adapter in
`app/services/live_cache.py`. The adapter exposes the required public
functions—`getLiveLine`, `getLiveLineHistory`, `getRateOfChange`, and
`getLiveBox`—without issuing additional paid API calls. Replace the JSON loader
with the production cache binding for deployment.

### Betting Insight Engine

The insight builder clamps pace calculations to a valid window (60–120) and
reuses the last good value if live pace is unstable before the two-minute mark.
It generates a one-line summary, market alignment, defensive context, bias
signals, and supporting metrics for the front-end card. Telemetry is logged for
every render with cache age, alignment, and summary length.

### Testing Checklist

- All 30 teams produce season profiles with defensive fields populated
- Pace guardrails prevent unrealistic spikes or dips
- Insight card always returns a summary sentence
- When the paid API is disabled the UI renders using cached snapshots

### Deployment Notes

The app is designed for Render deployment. Provide the environment variables
above and mount the `frontend` directory as static assets. Use the
`FEATURE_BETTING_INSIGHT` flag to gate rollout during the canary period.
