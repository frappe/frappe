import subprocess
from pathlib import Path

from flow_tui.client.state import ConversationState
from flow_tui.widgets.status_bar import repository_label


def test_repository_label_shows_directory_and_branch(tmp_path: Path):
	subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)

	assert repository_label(tmp_path) == f"{tmp_path.name} (main)"


def test_state_reads_working_directory_from_session_info(tmp_path: Path):
	state = ConversationState()
	state.seed({"config": {"cwd": str(tmp_path)}})

	assert state.cwd == str(tmp_path)
