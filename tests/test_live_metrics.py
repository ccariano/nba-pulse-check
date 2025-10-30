import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.append(str(ROOT))

from app.services.season_profiles import get_season_profiles
from app.services.live_metrics import build_insight


def test_build_insight_produces_summary():
    state = get_season_profiles()
    insight = build_insight("0022500001", state)
    assert isinstance(insight["summary"], str)
    assert insight["summary"].strip() != ""
    assert insight["alignment"] in {"above", "below", "aligned"}
