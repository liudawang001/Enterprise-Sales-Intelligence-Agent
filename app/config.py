"""Backward-compatible import surface for application settings."""

from app.settings.production import AuthMode, Settings, get_settings

__all__ = ["AuthMode", "Settings", "get_settings"]
