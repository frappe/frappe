import asyncio
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from flow.events import AssistantMessage, ToolCall, ToolResult, Usage, UserMessage, parse_event
from flow.model import Model
from flow.server import create_app
from flow.session.config import SessionConfig
from flow.session.prompt import build_system_prompt
from flow.session.skills import (
	MAX_SKILL_INDEX_BYTES,
	MAX_SKILLS,
	Skill,
	SkillError,
	discover_skills,
	format_skill_invocation,
	format_skills_for_prompt,
	parse_skill_command,
	parse_skill_invocation,
)
from flow.session.store import SessionStore
from flow.tools import BUILTIN_TOOLS
from flow.tools.tool import ToolContext


def _skill(root, name, description="Use for tests.", body="# Instructions\nRun the focused tests."):
	directory = root / name
	directory.mkdir(parents=True)
	path = directory / "SKILL.md"
	path.write_text(
		f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
		encoding="utf-8",
	)
	return path


def test_discovers_global_and_project_skills_with_project_precedence(tmp_path):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	_skill(home / ".agents" / "skills", "review", "Global review")
	project_path = _skill(project / ".agents" / "skills", "review", "Project review")
	_skill(project / ".agents" / "skills", "testing")

	catalog = discover_skills(str(project), home=str(home))

	assert [skill.name for skill in catalog.skills] == ["review", "testing"]
	review = next(skill for skill in catalog.skills if skill.name == "review")
	assert review.description == "Project review"
	assert review.path == str(project_path)
	assert len(catalog.diagnostics) == 1
	assert "overrid" in catalog.diagnostics[0].message


def test_default_skill_roots_scan_children_even_with_a_root_manifest(tmp_path):
	project = tmp_path / "project"
	root = project / ".agents" / "skills"
	root.mkdir(parents=True)
	(root / "SKILL.md").write_text(
		"---\nname: skills\ndescription: Root manifest\n---\nRoot body",
		encoding="utf-8",
	)
	_skill(root, "testing")

	catalog = discover_skills(str(project), home=str(tmp_path / "home"))

	assert [skill.name for skill in catalog.skills] == ["testing"]


def test_project_skill_symlink_obeys_allowed_roots(tmp_path):
	project = tmp_path / "project"
	outside = tmp_path / "outside"
	skill_dir = project / ".agents" / "skills" / "escaped"
	skill_dir.mkdir(parents=True)
	outside.mkdir()
	outside_skill = _skill(outside, "real")
	(skill_dir / "SKILL.md").symlink_to(outside_skill)

	catalog = discover_skills(
		str(project),
		home=str(tmp_path / "home"),
		allowed_roots=[str(project)],
	)

	assert catalog.skills == ()
	assert catalog.diagnostics[0].message == "skill is outside allowed roots"


def test_invalid_skill_is_diagnostic_and_not_loaded(tmp_path):
	root = tmp_path / ".agents" / "skills" / "broken"
	root.mkdir(parents=True)
	(root / "SKILL.md").write_text("# no frontmatter", encoding="utf-8")

	catalog = discover_skills(str(tmp_path), home=str(tmp_path / "home"))

	assert catalog.skills == ()
	assert "frontmatter" in catalog.diagnostics[0].message


def test_skill_name_must_match_parent_directory(tmp_path):
	directory = tmp_path / "wrong-folder"
	directory.mkdir()
	(directory / "SKILL.md").write_text(
		"---\nname: review\ndescription: Review code.\n---\nReview carefully.",
		encoding="utf-8",
	)

	catalog = discover_skills(str(tmp_path), enabled=False, extra_paths=[str(tmp_path)])

	assert catalog.skills == ()
	assert "must match parent directory" in catalog.diagnostics[0].message


def test_invalid_alias_does_not_hide_a_valid_lower_precedence_alias(tmp_path):
	lower = tmp_path / "lower"
	higher = tmp_path / "higher"
	path = _skill(lower, "review")
	alias = higher / "wrong-name"
	alias.mkdir(parents=True)
	(alias / "SKILL.md").symlink_to(path)

	catalog = discover_skills(
		str(tmp_path),
		enabled=False,
		extra_paths=[str(lower), str(higher)],
	)

	assert [skill.name for skill in catalog.skills] == ["review"]
	assert any("must match parent directory" in item.message for item in catalog.diagnostics)


def test_prompt_index_is_omitted_without_read_or_during_verbatim_override(tmp_path):
	path = _skill(tmp_path, "testing")
	catalog = discover_skills(str(tmp_path), enabled=False, extra_paths=[str(path)])

	without_read = build_system_prompt(
		SessionConfig(cwd=str(tmp_path), tools=["bash"]),
		skills=catalog.skills,
	)
	verbatim = build_system_prompt(
		SessionConfig(cwd=str(tmp_path), system_prompt="exact"),
		skills=catalog.skills,
	)

	assert "<available_skills>" not in without_read
	assert verbatim == "exact"


def test_prompt_index_escapes_metadata_and_hides_manual_only_skill(tmp_path):
	_skill(tmp_path, "visible", 'Use for <XML> & "quotes"')
	hidden = _skill(tmp_path, "hidden")
	hidden.write_text(
		"---\nname: hidden\ndescription: Hidden skill\ndisable-model-invocation: true\n---\nBody",
		encoding="utf-8",
	)
	catalog = discover_skills(str(tmp_path), home=str(tmp_path / "none"), extra_paths=[str(tmp_path)])

	formatted = format_skills_for_prompt(catalog.skills)

	assert "<name>visible</name>" in formatted
	assert "&lt;XML&gt; &amp; &quot;quotes&quot;" in formatted
	assert "<name>hidden</name>" not in formatted
	assert {skill.name for skill in catalog.skills} == {"visible", "hidden"}


def test_skill_command_supports_multiline_instructions(tmp_path):
	path = _skill(tmp_path, "testing")
	catalog = discover_skills(str(tmp_path), home=str(tmp_path / "none"), extra_paths=[str(path)])

	invocation = parse_skill_command("/skill:testing\n\nAdd parser tests", catalog.skills)

	assert invocation is not None
	assert invocation.content.startswith("# Instructions")
	assert invocation.instructions == "Add parser tests"
	assert parse_skill_command("ordinary prompt", catalog.skills) is None


async def test_explicit_invocation_is_ordinary_durable_user_text(tmp_path):
	project = tmp_path / "project"
	project.mkdir()
	_skill(project / ".agents" / "skills", "testing")
	session = SessionStore(str(tmp_path / "data")).create(SessionConfig(cwd=str(project)))

	handle = await session.run("/skill:testing add parser tests")
	assert handle.task is not None
	await handle.task

	message = next(
		entry for row in session.log.read_since(0) if isinstance((entry := parse_event(row)), UserMessage)
	)
	assert isinstance(message.content, str)
	assert '<skill name="testing"' in message.text
	assert message.text.endswith("add parser tests")
	parsed = parse_skill_invocation(message.text)
	assert parsed is not None
	assert parsed.name == "testing"
	assert parsed.instructions == "add parser tests"


def test_catalog_and_prompt_survive_restart(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	path = _skill(project / ".agents" / "skills", "testing", "Original description")
	data = str(tmp_path / "data")
	created = SessionStore(data).create(SessionConfig(cwd=str(project)))
	original_prompt = created.config.system_prompt
	path.write_text(
		"---\nname: testing\ndescription: Changed later\n---\nChanged",
		encoding="utf-8",
	)

	reloaded = SessionStore(data).get(created.id)

	assert reloaded.config.system_prompt == original_prompt
	assert reloaded.skill_catalog.skills[0].description == "Original description"


def test_persisted_catalog_obeys_a_tightened_allowed_root(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	outside = tmp_path / "outside"
	home.mkdir()
	project.mkdir()
	outside.mkdir()
	monkeypatch.setenv("HOME", str(home))
	outside_skill = _skill(outside, "review")
	alias = project / ".agents" / "skills" / "review"
	alias.mkdir(parents=True)
	(alias / "SKILL.md").symlink_to(outside_skill)
	data = str(tmp_path / "data")
	created = SessionStore(data, allowed_roots=[]).create(SessionConfig(cwd=str(project)))

	with pytest.raises(ValueError, match="stored skill 'review' is outside allowed roots"):
		SessionStore(data, allowed_roots=[str(project)]).get(created.id)


class _ReadsSkillModel(Model):
	def __init__(self, path):
		self.path = path
		self.calls = 0
		self.prompts = []

	async def run(self, request):
		self.calls += 1
		self.prompts.append(request.system_prompt)
		if self.calls == 1:
			yield AssistantMessage(
				content=[ToolCall(id="read-skill", name="read", arguments={"path": str(self.path)})],
				stop_reason="tool_use",
			)
		else:
			assert any(
				isinstance(message, ToolResult) and "Run the focused tests" in message.content
				for message in request.messages
			)
			yield AssistantMessage(content="used skill")
		yield Usage()


async def test_model_can_read_global_skill_without_granting_a_wider_project_root(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	path = _skill(home / ".agents" / "skills", "testing")
	store = SessionStore(str(tmp_path / "data"), allowed_roots=[str(project)])
	session = store.create(SessionConfig(cwd=str(project), auto_approve=True))
	model = _ReadsSkillModel(path)

	handle = await session.run("test this", model=model)
	assert handle.task is not None
	await handle.task

	assert model.calls == 2
	assert "<available_skills>" in model.prompts[0]


async def test_skill_read_roots_do_not_grant_write_access(tmp_path):
	project = tmp_path / "project"
	global_skills = tmp_path / "global-skills"
	project.mkdir()
	global_skills.mkdir()
	path = global_skills / "reference.txt"
	path.write_text("reference", encoding="utf-8")
	ctx = ToolContext(
		cwd=str(project),
		allowed_roots=(str(project),),
		read_only_roots=(str(global_skills),),
	)

	result = await BUILTIN_TOOLS["read"](path=str(path), ctx=ctx)
	assert result.content == "reference"
	grep_result = await BUILTIN_TOOLS["grep"](pattern="reference", path=str(global_skills), ctx=ctx)
	assert "reference.txt:1:reference" in grep_result.content
	with pytest.raises(PermissionError):
		await BUILTIN_TOOLS["write"](path=str(global_skills / "changed.txt"), content="no", ctx=ctx)


def test_explicit_skill_paths_obey_allowed_roots(tmp_path):
	project = tmp_path / "project"
	outside = tmp_path / "outside"
	project.mkdir()
	outside.mkdir()
	_skill(outside, "testing")
	store = SessionStore(str(tmp_path / "data"), allowed_roots=[str(project)])

	with pytest.raises(ValueError, match=r"skill path .* is not under an allowed root"):
		store.create(SessionConfig(cwd=str(project), skill_paths=[str(outside)]))


def test_skills_endpoint_and_unknown_command_error(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	_skill(project / ".agents" / "skills", "testing")
	data = tmp_path / "data"
	client = TestClient(create_app(SessionStore(str(data))))
	preview = client.post("/skills", json={"cwd": str(project)}).json()
	assert preview["skills"] == [{"name": "testing", "description": "Use for tests."}]
	assert list(data.rglob("*.meta.json")) == []
	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]

	catalog = client.get(f"/sessions/{sid}/skills").json()
	assert catalog["skills"] == [{"name": "testing", "description": "Use for tests."}]
	assert catalog["diagnostics"] == []
	response = client.post(f"/sessions/{sid}/run", json={"message": "/skill:missing"})
	assert response.status_code == 400
	assert response.json()["detail"] == "unknown skill: missing"


def test_explicit_skill_invocation_keeps_attachments(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	_skill(project / ".agents" / "skills", "testing")
	client = TestClient(create_app(SessionStore(str(tmp_path / "data"))))
	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	image = io.BytesIO()
	Image.new("RGB", (2, 2), "red").save(image, format="PNG")
	upload = client.post(
		f"/sessions/{sid}/attachments",
		files=[("files", ("screen.png", image.getvalue(), "image/png"))],
	).json()["attachments"][0]

	response = client.post(
		f"/sessions/{sid}/run?wait=true",
		json={"message": "/skill:testing inspect this", "attachments": [upload["id"]]},
	)

	assert response.status_code == 200
	entry = next(
		item
		for item in client.get(f"/sessions/{sid}/entries").json()["entries"]
		if item["type"] == "user_message"
	)
	assert [block["type"] for block in entry["content"]] == ["text", "attachment"]
	assert "skill" not in entry
	parsed = parse_skill_invocation(entry["content"][0]["text"])
	assert parsed is not None
	assert parsed.name == "testing"
	assert parsed.instructions == "inspect this"


def test_skill_manifest_is_private_json_sidecar(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	_skill(project / ".agents" / "skills", "testing")
	session = SessionStore(str(tmp_path / "data")).create(SessionConfig(cwd=str(project)))
	manifest = next((tmp_path / "data" / "sessions").rglob(f"{session.id}.skills.json"))

	payload = json.loads(manifest.read_text())
	assert payload["skills"][0]["name"] == "testing"
	assert manifest.stat().st_mode & 0o777 == 0o600


def test_global_symlinked_skill_directory_is_supported(tmp_path):
	home = tmp_path / "home"
	shared = tmp_path / "shared"
	global_root = home / ".agents" / "skills"
	global_root.mkdir(parents=True)
	path = _skill(shared, "review")
	(global_root / "review").symlink_to(path.parent, target_is_directory=True)

	catalog = discover_skills(str(tmp_path / "project"), home=str(home))

	assert [skill.name for skill in catalog.skills] == ["review"]
	assert catalog.skills[0].canonical_path == str(path.resolve())


def test_global_skill_child_symlink_obeys_configured_roots(tmp_path):
	home = tmp_path / "home"
	project = tmp_path / "project"
	outside = tmp_path / "outside"
	global_root = home / ".agents" / "skills"
	global_root.mkdir(parents=True)
	project.mkdir()
	path = _skill(outside, "review")
	(global_root / "review").symlink_to(path.parent, target_is_directory=True)

	catalog = discover_skills(
		str(project),
		home=str(home),
		allowed_roots=[str(project)],
	)

	assert catalog.skills == ()
	assert catalog.diagnostics[0].message == "skill is outside allowed roots"


def test_skill_limit_does_not_hide_project_override(tmp_path):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	for index in range(MAX_SKILLS):
		_skill(home / ".agents" / "skills", f"skill-{index:03d}", f"global {index}")
	_skill(project / ".agents" / "skills", "aaa-new", "project new")
	project_override = _skill(
		project / ".agents" / "skills",
		f"skill-{MAX_SKILLS - 1:03d}",
		"project override",
	)

	catalog = discover_skills(str(project), home=str(home))

	assert len(catalog.skills) == MAX_SKILLS
	override = next(skill for skill in catalog.skills if skill.name == f"skill-{MAX_SKILLS - 1:03d}")
	assert override.path == str(project_override)
	assert override.description == "project override"
	assert any("skill limit" in diagnostic.message for diagnostic in catalog.diagnostics)


def test_discovery_reads_only_bounded_frontmatter(tmp_path):
	path = tmp_path / "testing" / "SKILL.md"
	path.parent.mkdir()
	path.write_bytes(b"---\nname: testing\ndescription: Test things\n---\n" + b"x" * 20_000 + b"\xff")

	catalog = discover_skills(str(tmp_path), enabled=False, extra_paths=[str(path)])

	assert [skill.name for skill in catalog.skills] == ["testing"]
	with pytest.raises(SkillError, match="UTF-8"):
		parse_skill_command("/skill:testing", catalog.skills)


def test_prompt_index_has_an_aggregate_budget(tmp_path):
	for index in range(MAX_SKILLS):
		_skill(
			tmp_path,
			f"skill-{index:03d}",
			description=f"Use for {index}: " + "x" * 1000,
		)
	catalog = discover_skills(str(tmp_path), enabled=False, extra_paths=[str(tmp_path)])

	formatted = format_skills_for_prompt(catalog.skills)

	assert len(formatted.encode("utf-8")) <= MAX_SKILL_INDEX_BYTES
	assert formatted.count("<skill>") < MAX_SKILLS


def test_expanded_invocation_has_an_aggregate_budget(tmp_path):
	path = _skill(tmp_path, "large", body="x" * 200_000)
	catalog = discover_skills(str(tmp_path), enabled=False, extra_paths=[str(path)])

	with pytest.raises(SkillError, match="expanded skill exceeds"):
		parse_skill_command(f"/skill:large {'y' * 100_000}", catalog.skills)


def test_existing_session_reads_current_skill_body(tmp_path):
	project = tmp_path / "project"
	project.mkdir()
	path = _skill(project / ".agents" / "skills", "testing", body="Original body")
	session = SessionStore(str(tmp_path / "data")).create(SessionConfig(cwd=str(project)))
	path.write_text(
		"---\nname: testing\ndescription: Use for tests.\n---\nUpdated body",
		encoding="utf-8",
	)

	invocation = parse_skill_command("/skill:testing", session.skill_catalog.skills)

	assert invocation is not None
	assert "Updated body" in format_skill_invocation(invocation)


def test_skill_added_after_session_creation_is_invocable(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	_skill(project / ".agents" / "skills", "testing")
	data = str(tmp_path / "data")
	store = SessionStore(data)
	client = TestClient(create_app(store))
	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]
	_skill(project / ".agents" / "skills", "review", "Added later")

	listed = client.get(f"/sessions/{sid}/skills").json()["skills"]
	response = client.post(f"/sessions/{sid}/run?wait=true", json={"message": "/skill:review"})

	assert response.status_code == 200
	assert [skill["name"] for skill in listed] == ["review", "testing"]
	# invoking adopts it, so its directory keeps its read root across a restart
	assert [skill.name for skill in SessionStore(data).get(sid).skill_catalog.skills] == [
		"review",
		"testing",
	]
	# the prompt the model sees was composed once and does not gain the new skill
	assert "Added later" not in store.get(sid).config.system_prompt


def test_resolved_skill_refuses_a_path_swapped_since_discovery(tmp_path):
	project = tmp_path / "project"
	project.mkdir()
	path = _skill(project / ".agents" / "skills", "review")
	# what discovery recorded no longer resolves to the file about to be opened
	swapped = Skill(
		name="review",
		description="Use for tests.",
		path=str(path),
		canonical_path=str(tmp_path / "elsewhere" / "SKILL.md"),
	)

	with pytest.raises(SkillError, match="skill path changed: review"):
		parse_skill_command("/skill:review", (), resolve=lambda name: swapped)


def test_late_skill_outside_allowed_roots_is_not_invocable(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	outside = tmp_path / "outside"
	home.mkdir()
	project.mkdir()
	outside.mkdir()
	monkeypatch.setenv("HOME", str(home))
	store = SessionStore(str(tmp_path / "data"), allowed_roots=[str(project)])
	session = store.create(SessionConfig(cwd=str(project)))
	outside_skill = _skill(outside, "review")
	alias = project / ".agents" / "skills" / "review"
	alias.mkdir(parents=True)
	(alias / "SKILL.md").symlink_to(outside_skill)

	assert store.resolve_skill(session.config, "review") is None
	with pytest.raises(SkillError, match="unknown skill: review"):
		parse_skill_command(
			"/skill:review",
			session.skill_catalog.skills,
			resolve=lambda name: store.resolve_skill(session.config, name),
		)


class _SteeringSkillModel(Model):
	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()
		self.calls = 0
		self.saw_skill = False

	async def run(self, request):
		self.calls += 1
		if self.calls == 1:
			self.started.set()
			await self.release.wait()
		else:
			self.saw_skill = any(
				isinstance(message, UserMessage) and parse_skill_invocation(message.text) is not None
				for message in request.messages
			)
		yield AssistantMessage(content="done")
		yield Usage()


async def test_skill_invocation_can_steer_an_active_run(tmp_path):
	project = tmp_path / "project"
	project.mkdir()
	_skill(project / ".agents" / "skills", "testing")
	session = SessionStore(str(tmp_path / "data")).create(SessionConfig(cwd=str(project)))
	model = _SteeringSkillModel()

	first = await session.run("start", model=model)
	await model.started.wait()
	steering = await session.run("/skill:testing focus here")
	assert steering.status == "steered"
	model.release.set()
	assert first.task is not None
	await first.task

	assert model.calls == 2
	assert model.saw_skill


class _CapturingModel(Model):
	def __init__(self):
		self.requests = []

	async def run(self, request):
		self.requests.append(request)
		yield AssistantMessage(content="summary")
		yield Usage()


async def test_compaction_summarizes_expanded_skill_as_ordinary_user_text(tmp_path):
	project = tmp_path / "project"
	project.mkdir()
	_skill(project / ".agents" / "skills", "testing")
	session = SessionStore(str(tmp_path / "data")).create(SessionConfig(cwd=str(project)))
	model = _CapturingModel()

	run = await session.run("/skill:testing focus here", model=model)
	assert run.task is not None
	await run.task
	compaction = await session.compact(model=model)
	assert compaction.task is not None
	await compaction.task

	summary_prompt = model.requests[-1].messages[0].text
	assert '<skill name="testing"' in summary_prompt
	assert "focus here" in summary_prompt


def test_skill_title_uses_additional_instructions(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	_skill(project / ".agents" / "skills", "testing")
	client = TestClient(create_app(SessionStore(str(tmp_path / "data"))))
	sid = client.post("/sessions", json={"cwd": str(project)}).json()["session_id"]

	response = client.post(
		f"/sessions/{sid}/run?wait=true",
		json={"message": "/skill:testing add parser coverage"},
	)

	assert response.status_code == 200
	assert client.get(f"/sessions/{sid}").json()["title"] == "add parser coverage"
