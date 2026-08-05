import subprocess
from pathlib import Path

from textual.app import App, ComposeResult

from flow_tui.client.state import ConversationState
from flow_tui.widgets.status_bar import StatusBar, compact_number, repository_label


def test_compact_number_rounds_large_values():
	assert compact_number(999) == "999"
	assert compact_number(1_500) == "1.5k"
	assert compact_number(2_000_000) == "2M"


class StatusApp(App):
	def compose(self) -> ComposeResult:
		yield StatusBar()


async def test_status_bar_shows_absolute_context_and_unlabelled_effort(tmp_path: Path):
	state = ConversationState()
	state.cwd = str(tmp_path)
	state.model = "codex/gpt-5"
	state.reasoning_effort = "high"
	state.context_tokens = 5_000
	state.context_window = 256_000
	state.input_tokens = 12_000
	state.output_tokens = 3_000
	async with StatusApp().run_test() as pilot:
		bar = pilot.app.query_one(StatusBar)
		bar.refresh_from(state)
		line = str(bar.render())

		assert "5k/256k" in line
		assert "↑12k · ↓3k" in line
		assert line.endswith("codex/gpt-5 · high")
		assert "effort:" not in line


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
