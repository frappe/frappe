import json

from fastapi.testclient import TestClient

from flow.server import create_app
from flow.session.config import SessionConfig
from flow.session.prompt import DEFAULT_INTRO, build_system_prompt
from flow.session.store import SessionStore


def _home(tmp_path):
	home = tmp_path / "home"
	home.mkdir()
	return home


def test_default_compose_shape(tmp_path):
	home = _home(tmp_path)
	config = SessionConfig(cwd=str(tmp_path / "work"))
	prompt = build_system_prompt(config, home=str(home))
	assert prompt.startswith(DEFAULT_INTRO)
	assert "Available tools:" in prompt
	assert "- bash: " in prompt
	assert "- read: " in prompt
	assert "Guidelines:" in prompt
	assert "- Be concise in your responses" in prompt
	assert prompt.endswith(f"Current working directory: {tmp_path / 'work'}")
	assert "<project_context>" not in prompt


def test_tools_list_follows_config(tmp_path):
	home = _home(tmp_path)
	config = SessionConfig(cwd=str(tmp_path), tools=["read", "grep"])
	prompt = build_system_prompt(config, home=str(home))
	assert "- read: " in prompt
	assert "- grep: " in prompt
	assert "- bash: " not in prompt
	assert "- edit: " not in prompt
	# guidelines follow the active tools too
	assert "Use read to examine files" in prompt
	assert "Use write only" not in prompt


def test_global_agents_md_included_with_provenance(tmp_path):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("always use tabs")
	config = SessionConfig(cwd=str(tmp_path / "work"))
	prompt = build_system_prompt(config, home=str(home))
	assert prompt.startswith(DEFAULT_INTRO)
	assert "<project_context>" in prompt
	assert f'<project_instructions path="{home / "AGENTS.md"}">' in prompt
	assert "always use tabs" in prompt


def test_project_chain_outermost_first(tmp_path):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("global rules")
	repo = home / "repo"
	sub = repo / "pkg" / "sub"
	sub.mkdir(parents=True)
	(repo / ".git").mkdir()
	(repo / "AGENTS.md").write_text("repo rules")
	(sub / "AGENTS.md").write_text("sub rules")
	config = SessionConfig(cwd=str(sub))
	prompt = build_system_prompt(config, home=str(home))
	order = [prompt.index(marker) for marker in ("global rules", "repo rules", "sub rules")]
	assert order == sorted(order)
	assert f'<project_instructions path="{repo / "AGENTS.md"}">' in prompt
	assert f'<project_instructions path="{sub / "AGENTS.md"}">' in prompt


def test_walk_stops_at_git_root(tmp_path):
	home = _home(tmp_path)
	outer = tmp_path / "outer"
	repo = outer / "repo"
	repo.mkdir(parents=True)
	(repo / ".git").mkdir()
	(outer / "AGENTS.md").write_text("outside the repo")
	(repo / "AGENTS.md").write_text("repo rules")
	config = SessionConfig(cwd=str(repo))
	prompt = build_system_prompt(config, home=str(home))
	assert "repo rules" in prompt
	assert "outside the repo" not in prompt


def test_cwd_at_home_reads_agents_md_once(tmp_path):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("home rules")
	config = SessionConfig(cwd=str(home))
	prompt = build_system_prompt(config, home=str(home))
	assert prompt.count("home rules") == 1
	assert prompt.count("<project_instructions") == 1


def test_git_file_marks_a_worktree_root(tmp_path):
	home = _home(tmp_path)
	(tmp_path / "AGENTS.md").write_text("outside the worktree")
	worktree = tmp_path / "wt"
	worktree.mkdir()
	(worktree / ".git").write_text("gitdir: /elsewhere")
	(worktree / "AGENTS.md").write_text("worktree rules")
	config = SessionConfig(cwd=str(worktree))
	prompt = build_system_prompt(config, home=str(home))
	assert "worktree rules" in prompt
	assert "outside the worktree" not in prompt


def test_empty_and_missing_agents_md_are_skipped(tmp_path):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("   \n\n")
	config = SessionConfig(cwd=str(tmp_path / "nowhere"))
	prompt = build_system_prompt(config, home=str(home))
	assert "<project_context>" not in prompt


def test_preamble_override_and_suffix(tmp_path):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("global rules")
	config = SessionConfig(
		cwd=str(tmp_path),
		system_preamble="short preamble",
		system_suffix="client notes",
	)
	prompt = build_system_prompt(config, home=str(home))
	assert prompt.startswith("short preamble")
	assert DEFAULT_INTRO not in prompt
	assert "Available tools:" not in prompt
	# suffix comes before the context block and cwd trailer, like pi's append prompt
	assert prompt.index("client notes") < prompt.index("global rules")
	assert prompt.endswith(f"Current working directory: {tmp_path}")


def test_verbatim_system_prompt_skips_composition(tmp_path):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("must not appear")
	config = SessionConfig(
		cwd=str(tmp_path),
		system_prompt="exact prompt",
		system_suffix="also ignored",
	)
	assert build_system_prompt(config, home=str(home)) == "exact prompt"


def test_store_composes_once_and_persists(tmp_path, monkeypatch):
	home = _home(tmp_path)
	monkeypatch.setenv("HOME", str(home))
	project = tmp_path / "project"
	project.mkdir()
	(project / "AGENTS.md").write_text("project rules")
	data_dir = str(tmp_path / "data")
	session = SessionStore(data_dir).create(SessionConfig(cwd=str(project)))
	assert "project rules" in session.config.system_prompt

	# an AGENTS.md edit after create must not change the session
	(project / "AGENTS.md").write_text("changed later")
	reloaded = SessionStore(data_dir).get(session.id)
	assert reloaded.config.system_prompt == session.config.system_prompt

	meta_path = next((tmp_path / "data" / "sessions").rglob(f"{session.id}.meta.json"))
	meta = json.loads(meta_path.read_text())
	assert "project rules" in meta["system_prompt"]


def test_server_reports_composed_prompt(tmp_path, monkeypatch):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("global rules")
	monkeypatch.setenv("HOME", str(home))
	c = TestClient(create_app(SessionStore(str(tmp_path / "data"))))
	created = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()
	prompt = created["config"]["system_prompt"]
	assert prompt.startswith(DEFAULT_INTRO)
	assert "global rules" in prompt
	got = c.get(f"/sessions/{created['session_id']}").json()
	assert got["config"]["system_prompt"] == prompt


def test_append_lands_after_the_cwd_trailer(tmp_path):
	home = _home(tmp_path)
	config = SessionConfig(cwd=str(tmp_path), system_append="stay terse")
	prompt = build_system_prompt(config, home=str(home))
	assert prompt.startswith(DEFAULT_INTRO)
	assert prompt.endswith("stay terse")
	assert prompt.index(f"Current working directory: {tmp_path}") < prompt.index("stay terse")


def test_append_applies_to_a_verbatim_prompt(tmp_path):
	home = _home(tmp_path)
	config = SessionConfig(cwd=str(tmp_path), system_prompt="exact prompt", system_append="stay terse")
	assert build_system_prompt(config, home=str(home)) == "exact prompt\n\nstay terse"


def test_blank_append_changes_nothing(tmp_path):
	home = _home(tmp_path)
	base = build_system_prompt(SessionConfig(cwd=str(tmp_path)), home=str(home))
	config = SessionConfig(cwd=str(tmp_path), system_append="  \n")
	assert build_system_prompt(config, home=str(home)) == base


def test_server_append_option_joins_the_client_append(tmp_path, monkeypatch):
	monkeypatch.setenv("HOME", str(_home(tmp_path)))
	c = TestClient(create_app(SessionStore(str(tmp_path / "data")), system_append="operator rules"))
	created = c.post(
		"/sessions", json={"model": "mock", "cwd": str(tmp_path), "system_append": "client rules"}
	).json()
	prompt = created["config"]["system_prompt"]
	assert prompt.endswith("client rules\n\noperator rules")
