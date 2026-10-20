import os

import pytest
from fastapi.testclient import TestClient

from flow_harness import settings
from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.session.store import SessionStore


@pytest.fixture
def settings_path(tmp_path, monkeypatch):
	path = tmp_path / "prefs" / "settings.json"
	monkeypatch.setattr(settings, "SETTINGS_PATH", str(path))
	return path


def test_settings_save_privately_and_tolerate_a_missing_or_corrupt_file(settings_path, tmp_path):
	assert settings.load_settings() == {}
	assert settings.last_model() is None
	settings_path.parent.mkdir(parents=True)
	settings_path.write_text("{not json")
	assert settings.load_settings() == {}

	settings.save_setting("last_model", "openai/gpt-x")
	assert settings.last_model() == "openai/gpt-x"
	settings.save_setting("other", 1)
	assert settings.load_settings() == {"last_model": "openai/gpt-x", "other": 1}
	assert oct(os.stat(settings_path).st_mode & 0o777) == "0o600"
	# a remembered model must be a non-empty name
	for value in (42, ""):
		settings.save_setting("last_model", value)
		assert settings.last_model() is None, value

	# the web UI's settings sit in their own entry, merged key by key
	store = SessionStore(
		str(tmp_path / "data"), credential_store=CredentialStore(str(tmp_path / "credentials.json"))
	)
	client = TestClient(create_app(store))
	assert client.get("/settings").json() == {"settings": None}
	client.patch("/settings", json={"settings": {"theme": "dark", "mode": "ask"}})
	assert client.patch("/settings", json={"settings": {"mode": "auto"}}).json() == {
		"settings": {"theme": "dark", "mode": "auto"}
	}
	assert client.get("/settings").json() == {"settings": {"theme": "dark", "mode": "auto"}}
	assert settings.load_settings()["other"] == 1
	assert client.patch("/settings", json={"settings": ["dark"]}).status_code == 422


def test_startup_model_precedence(settings_path, monkeypatch):
	monkeypatch.delenv("FLOW_MODEL", raising=False)
	assert settings.resolve_startup_model() == "mock"
	settings.save_setting("last_model", "remembered")
	assert settings.resolve_startup_model() == "remembered"
	monkeypatch.setenv("FLOW_MODEL", "from-env")
	assert settings.resolve_startup_model() == "from-env"
