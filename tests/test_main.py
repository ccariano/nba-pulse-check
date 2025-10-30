"""Tests for FastAPI application entry points."""

from pathlib import Path

from fastapi.responses import FileResponse

from app.main import index


def test_root_serves_frontend_index() -> None:
    """Root endpoint should serve the static frontend index file."""

    response = index()

    assert isinstance(response, FileResponse)
    assert response.status_code == 200
    expected_path = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
    assert Path(response.path).resolve() == expected_path
