import os

import pytest

from flow_harness import settings
from flow_harness.session import workspaces

# litellm's bundled model map; the live one changes upstream without notice
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


@pytest.fixture(autouse=True)
def _private_settings_file(tmp_path_factory, monkeypatch):
	"""No test writes the user's ~/.flow/settings.json, even when the code it tests breaks."""
	monkeypatch.setattr(settings, "SETTINGS_PATH", str(tmp_path_factory.mktemp("settings") / "settings.json"))


@pytest.fixture(autouse=True)
def _private_default_workspace(tmp_path_factory, monkeypatch):
	"""No test makes the user's ~/Documents/flow/default-workspace."""
	monkeypatch.setattr(
		workspaces, "DEFAULT_WORKSPACE", str(tmp_path_factory.mktemp("home") / "default-workspace")
	)
