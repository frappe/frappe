import json
import os
import re

from fastapi.testclient import TestClient

from flow_harness.events import AssistantMessage, ToolCall, ToolResult, Usage
from flow_harness.model import Model
from flow_harness.server import create_app
from flow_harness.session.config import SessionConfig
from flow_harness.session.prompt import DEFAULT_INTRO, _docs_dir, build_system_prompt
from flow_harness.session.store import SessionStore


def _home(tmp_path):
	home = tmp_path / "home"
	home.mkdir()
	return home


def test_default_body_follows_the_active_tools(tmp_path):
	home = _home(tmp_path)
	prompt = build_system_prompt(SessionConfig(cwd=str(tmp_path / "work")), home=str(home))
	assert prompt.startswith(DEFAULT_INTRO)
	assert "Available tools:" in prompt
	assert "- bash: " in prompt
	assert "- read: " in prompt
	assert "Guidelines:" in prompt
	assert "- Be concise in your responses" in prompt
	assert prompt.endswith(f"Current working directory: {tmp_path / 'work'}")
	assert "<project_context>" not in prompt
	docs = _docs_dir("docs")
	assert docs is not None and os.path.isfile(os.path.join(docs, "extensions.md"))
	assert f"- Docs: {docs}" in prompt
	assert "docs/extensions.md" in prompt
	examples = _docs_dir("examples")
	assert examples is not None and os.path.isdir(os.path.join(examples, "extensions"))
	assert f"- Examples: {examples}" in prompt

	narrow = build_system_prompt(SessionConfig(cwd=str(tmp_path), tools=["read", "grep"]), home=str(home))
	assert "- read: " in narrow
	assert "- grep: " in narrow
	assert "- bash: " not in narrow
	assert "- edit: " not in narrow
	# guidelines follow the active tools too
	assert "Use read to examine files" in narrow
	assert "Use write only" not in narrow
	# the docs pointer needs a tool that can read them
	write_only = SessionConfig(cwd=str(tmp_path), tools=["write"])
	assert "Flow documentation" not in build_system_prompt(write_only, home=str(home))


def test_project_context_reads_agents_md_from_home_down_to_the_cwd(tmp_path):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("global rules")
	outer = home / "outer"
	repo = outer / "repo"
	sub = repo / "pkg" / "sub"
	sub.mkdir(parents=True)
	(outer / "AGENTS.md").write_text("outside the repo")
	(repo / ".git").mkdir()
	(repo / "AGENTS.md").write_text("repo rules")
	(repo / "pkg" / "AGENTS.md").write_text("   \n\n")
	(sub / "AGENTS.md").write_text("sub rules")
	worktree = outer / "wt"
	worktree.mkdir()
	(worktree / ".git").write_text("gitdir: /elsewhere")
	(worktree / "AGENTS.md").write_text("worktree rules")
	cases = [
		# outermost first; the walk stops at the git root and skips an empty file
		(sub, [(home, "global rules"), (repo, "repo rules"), (sub, "sub rules")]),
		# a .git file marks a worktree root
		(worktree, [(home, "global rules"), (worktree, "worktree rules")]),
		# at home, its AGENTS.md is read once
		(home, [(home, "global rules")]),
	]
	for cwd, expected in cases:
		prompt = build_system_prompt(SessionConfig(cwd=str(cwd)), home=str(home))
		assert prompt.startswith(DEFAULT_INTRO), cwd
		assert "<project_context>" in prompt, cwd
		found = re.findall(r'<project_instructions path="([^"]+)">\n(.*?)\n</project_instructions>', prompt)
		assert found == [(str(directory / "AGENTS.md"), text) for directory, text in expected], cwd


def test_overrides_and_append_compose_in_order(tmp_path):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("global rules")
	trailer = f"Current working directory: {tmp_path}"
	config = SessionConfig(cwd=str(tmp_path), system_preamble="short preamble", system_suffix="client notes")
	prompt = build_system_prompt(config, home=str(home))
	assert prompt.startswith("short preamble")
	assert DEFAULT_INTRO not in prompt
	assert "Available tools:" not in prompt
	# the docs pointer is part of the composed body, so a preamble replaces it
	assert "Flow documentation" not in prompt
	# suffix comes before the context block and cwd trailer, like pi's append prompt
	assert prompt.index("client notes") < prompt.index("global rules")
	assert prompt.endswith(trailer)

	verbatim = SessionConfig(cwd=str(tmp_path), system_prompt="exact prompt", system_suffix="also ignored")
	assert build_system_prompt(verbatim, home=str(home)) == "exact prompt"

	# an append lands last, on a composed or a verbatim prompt; a blank one changes nothing
	appended = build_system_prompt(
		SessionConfig(cwd=str(tmp_path), system_append="stay terse"), home=str(home)
	)
	assert appended.startswith(DEFAULT_INTRO)
	assert appended.endswith("stay terse")
	assert appended.index(trailer) < appended.index("stay terse")
	verbatim = SessionConfig(cwd=str(tmp_path), system_prompt="exact prompt", system_append="stay terse")
	assert build_system_prompt(verbatim, home=str(home)) == "exact prompt\n\nstay terse"
	base = build_system_prompt(SessionConfig(cwd=str(tmp_path)), home=str(home))
	blank = SessionConfig(cwd=str(tmp_path), system_append="  \n")
	assert build_system_prompt(blank, home=str(home)) == base


def test_a_session_prompt_is_composed_once_at_create(tmp_path, monkeypatch):
	home = _home(tmp_path)
	(home / "AGENTS.md").write_text("global rules")
	monkeypatch.setenv("HOME", str(home))
	project = tmp_path / "project"
	project.mkdir()
	(project / "AGENTS.md").write_text("project rules")
	data = str(tmp_path / "data")
	c = TestClient(create_app(SessionStore(data), system_append="operator rules"))
	created = c.post(
		"/sessions", json={"model": "mock", "cwd": str(project), "system_append": "client rules"}
	).json()
	sid = created["session_id"]
	prompt = created["config"]["system_prompt"]
	assert prompt.startswith(DEFAULT_INTRO)
	assert "global rules" in prompt and "project rules" in prompt
	# the server's append option joins the client's
	assert prompt.endswith("client rules\n\noperator rules")
	assert c.get(f"/sessions/{sid}").json()["config"]["system_prompt"] == prompt

	# an AGENTS.md edit after create must not change the session
	(project / "AGENTS.md").write_text("changed later")
	assert SessionStore(data).get(sid).config.system_prompt == prompt
	meta_path = next((tmp_path / "data" / "sessions").rglob(f"{sid}.meta.json"))
	assert json.loads(meta_path.read_text())["system_prompt"] == prompt


class _ReadsDocsModel(Model):
	def __init__(self, path):
		self.path = path
		self.calls = 0
		self.results = []

	async def run(self, request):
		self.calls += 1
		if self.calls == 1:
			yield AssistantMessage(
				content=[ToolCall(id="read-docs", name="read", arguments={"path": self.path})],
				stop_reason="tool_use",
			)
		else:
			self.results.extend(m.content for m in request.messages if isinstance(m, ToolResult))
			yield AssistantMessage(content="read the docs")
		yield Usage()


async def test_fenced_session_can_read_the_docs_its_prompt_names(tmp_path):
	project = tmp_path / "project"
	project.mkdir()
	docs = _docs_dir("docs")
	assert docs is not None
	store = SessionStore(str(tmp_path / "data"), allowed_roots=[str(project)])
	session = store.create(SessionConfig(cwd=str(project), auto_approve=True))
	model = _ReadsDocsModel(os.path.join(docs, "extensions.md"))

	handle = await session.run("how do I write an extension?", model=model)
	assert handle.task is not None
	await handle.task

	assert model.calls == 2
	assert model.results and model.results[0].startswith("# Extensions")
