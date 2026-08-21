from __future__ import annotations

from core.settings import get_settings


def test_settings_load():
    settings = get_settings()
    assert settings.project_name is not None
    assert settings.port == 8000
    assert settings.use_mock_ai_fallback is True
