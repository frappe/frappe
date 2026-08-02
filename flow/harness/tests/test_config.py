import os

from flow import config


def test_server_state_defaults_are_user_global():
	assert config.DEFAULT_DATA_DIR == os.path.expanduser("~/.flow/server")
	assert config.DEFAULT_CREDENTIALS_PATH == os.path.expanduser("~/.flow/server/credentials.json")
	assert os.path.dirname(config.DEFAULT_CREDENTIALS_PATH) == config.DEFAULT_DATA_DIR
