import pandas as pd

from app.services.season_profiles import _prepare_four_factors_frame


def test_prepare_four_factors_frame_aliases_columns():
    frame = pd.DataFrame(
        [
            {
                "TEAM_ID": 1610612737,
                "OPP_EFG_PCT": 0.52,
                "OPP_TOV_PCT": 0.15,
                "DREB_PCT": 0.72,
                "OPP_FTA_RATE": 0.21,
            }
        ]
    )

    prepared = _prepare_four_factors_frame(frame)

    assert "DRB_PCT" in prepared.columns
    assert "OPP_FT_RATE" in prepared.columns
    assert prepared.loc[0, "DRB_PCT"] == frame.loc[0, "DREB_PCT"]
    assert prepared.loc[0, "OPP_FT_RATE"] == frame.loc[0, "OPP_FTA_RATE"]


def test_prepare_four_factors_frame_defaults_missing_columns(caplog):
    frame = pd.DataFrame(
        [
            {
                "TEAM_ID": 1610612737,
                "OPP_EFG_PCT": 0.52,
                "OPP_TOV_PCT": 0.15,
            }
        ]
    )

    with caplog.at_level("WARNING"):
        prepared = _prepare_four_factors_frame(frame)

    assert "DRB_PCT" in prepared.columns
    assert "OPP_FT_RATE" in prepared.columns
    assert prepared.loc[0, "DRB_PCT"] == 0.0
    assert prepared.loc[0, "OPP_FT_RATE"] == 0.0
    assert "missing columns" in caplog.text
