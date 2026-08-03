import os

import pytest

from flow import settings


@pytest.fixture
def settings_path(tmp_path, monkeypatch):
	path = tmp_path / "prefs" / "settings.json"
	monkeypatch.setattr(settings, "SETTINGS_PATH", str(path))
	return path


def test_missing_file_means_no_preferences(settings_path):
	assert settings.load_settings() == {}
	assert settings.last_model() is None


def test_save_and_load_roundtrip(settings_path):
	settings.save_setting("last_model", "openai/gpt-x")
	assert settings.last_model() == "openai/gpt-x"
	settings.save_setting("other", 1)
	assert settings.load_settings() == {"last_model": "openai/gpt-x", "other": 1}
	assert oct(os.stat(settings_path).st_mode & 0o777) == "0o600"


def test_corrupt_file_is_tolerated(settings_path):
	settings_path.parent.mkdir(parents=True)
	settings_path.write_text("{not json")
	assert settings.load_settings() == {}
	settings.save_setting("last_model", "m")
	assert settings.last_model() == "m"


def test_non_string_last_model_is_ignored(settings_path):
	settings.save_setting("last_model", 42)
	assert settings.last_model() is None
	settings.save_setting("last_model", "")
	assert settings.last_model() is None


def test_startup_model_precedence(settings_path, monkeypatch):
	monkeypatch.delenv("FLOW_MODEL", raising=False)
	assert settings.resolve_startup_model() == "mock"
	settings.save_setting("last_model", "remembered")
	assert settings.resolve_startup_model() == "remembered"
	monkeypatch.setenv("FLOW_MODEL", "from-env")
	assert settings.resolve_startup_model() == "from-env"
