"""
Static asset loader for the Smart Home web dashboard.
"""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "static"

STATIC_ASSETS: dict[str, str] = {
    "index.html": "text/html; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
}

DASHBOARD_HTML: str = (STATIC_DIR / "index.html").read_text(encoding="utf-8")


def load_static_asset(filename: str) -> tuple[bytes, str] | None:
    """
    Load an allowlisted dashboard asset by filename.
    Returns (payload_bytes, content_type) or None if not found/not allowed.
    """
    content_type = STATIC_ASSETS.get(filename)
    if content_type is None:
        return None
    asset_path = STATIC_DIR / filename
    if not asset_path.is_file():
        return None
    return asset_path.read_bytes(), content_type
