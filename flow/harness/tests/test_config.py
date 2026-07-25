import inspect
import os

from flow_server import config
from flow_server.agent import Agent


def test_server_state_defaults_are_user_global():
	assert config.DEFAULT_DATA_DIR == os.path.expanduser("~/.flow/server")
	assert config.DEFAULT_CREDENTIALS_PATH == os.path.expanduser(
		"~/.flow/credentials.json"
	)
	assert os.path.dirname(config.DEFAULT_CREDENTIALS_PATH) != config.DEFAULT_DATA_DIR
	assert inspect.signature(Agent).parameters["data_dir"].default == config.DATA_DIR
