import subprocess
from pathlib import Path

from flow_tui.client.state import ConversationState
from flow_tui.widgets.status_bar import compact_number, repository_label


def test_compact_number_rounds_large_values():
	assert compact_number(999) == "999"
	assert compact_number(1_500) == "1.5k"
	assert compact_number(2_000_000) == "2M"


def test_repository_label_shows_directory_and_branch(tmp_path: Path):
	subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)

	assert repository_label(tmp_path) == f"{tmp_path.name} (main)"


def test_repository_label_marks_dirty_worktree(tmp_path: Path):
	subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
	(tmp_path / "new.txt").write_text("dirty")

	assert repository_label(tmp_path) == f"{tmp_path.name} (main*)"


def test_state_reads_working_directory_from_session_info(tmp_path: Path):
	state = ConversationState()
	state.seed({"config": {"cwd": str(tmp_path)}})

	assert state.cwd == str(tmp_path)
