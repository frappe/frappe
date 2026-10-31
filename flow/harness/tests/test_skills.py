import asyncio
import io
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from flow_harness.events import AssistantMessage, ToolCall, ToolResult, Usage, UserMessage, parse_event
from flow_harness.model import Model
from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.session.config import SessionConfig
from flow_harness.session.prompt import build_system_prompt
from flow_harness.session.skills import (
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
from flow_harness.session.store import SessionStore
from flow_harness.tools import BUILTIN_TOOLS, BUNDLED_TOOLS
from flow_harness.tools.tool import ToolContext


def _skill(root, name, description="Use for tests.", body="# Instructions\nRun the focused tests."):
	directory = root / name
	directory.mkdir(parents=True)
	path = directory / "SKILL.md"
	path.write_text(
		f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
		encoding="utf-8",
	)
	return path


def test_discovery_prefers_project_skills_and_follows_symlinks(tmp_path):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	_skill(home / ".agents" / "skills", "review", "Global review")
	project_path = _skill(project / ".agents" / "skills", "review", "Project review")
	_skill(project / ".agents" / "skills", "testing")
	# a default root scans its children even when it holds a SKILL.md itself
	(project / ".agents" / "skills" / "SKILL.md").write_text(
		"---\nname: skills\ndescription: Root manifest\n---\nRoot body",
		encoding="utf-8",
	)
	shared = _skill(tmp_path / "shared", "linked")
	(home / ".agents" / "skills" / "linked").symlink_to(shared.parent, target_is_directory=True)

	catalog = discover_skills(str(project), home=str(home))

	assert [skill.name for skill in catalog.skills] == ["linked", "review", "testing"]
	review = next(skill for skill in catalog.skills if skill.name == "review")
	assert review.description == "Project review"
	assert review.path == str(project_path)
	assert catalog.skills[0].canonical_path == str(shared.resolve())
	assert len(catalog.diagnostics) == 1
	assert "overrid" in catalog.diagnostics[0].message


def test_an_invalid_skill_is_a_diagnostic_and_hides_nothing(tmp_path):
	lower = tmp_path / "lower"
	higher = tmp_path / "higher"
	path = _skill(lower, "review")
	# an alias under the wrong name must not hide the valid skill it points to
	alias = higher / "wrong-name"
	alias.mkdir(parents=True)
	(alias / "SKILL.md").symlink_to(path)
	for name, text in (
		("broken", "# no frontmatter"),
		("bad-yaml", "---\nname: bad-yaml\ndescription: a: b\n---\n"),
	):
		(higher / name).mkdir()
		(higher / name / "SKILL.md").write_text(text, encoding="utf-8")

	catalog = discover_skills(str(tmp_path), enabled=False, extra_paths=[str(lower), str(higher)])

	assert [skill.path for skill in catalog.skills] == [str(path)]
	messages = [item.message for item in catalog.diagnostics]
	for expected in ("must match parent directory", "requires YAML frontmatter", "invalid skill frontmatter"):
		assert any(expected in message for message in messages), expected


def test_discovery_refuses_symlinks_out_of_the_allowed_roots(tmp_path):
	home = tmp_path / "home"
	project = tmp_path / "project"
	outside = tmp_path / "outside"
	# a project skill file and a global skill directory, both linked from outside
	project_alias = project / ".agents" / "skills" / "escaped"
	project_alias.mkdir(parents=True)
	(project_alias / "SKILL.md").symlink_to(_skill(outside, "escaped"))
	global_root = home / ".agents" / "skills"
	global_root.mkdir(parents=True)
	(global_root / "review").symlink_to(_skill(outside, "review").parent, target_is_directory=True)

	catalog = discover_skills(str(project), home=str(home), allowed_roots=[str(project)])

	assert catalog.skills == ()
	assert [item.message for item in catalog.diagnostics] == ["skill is outside allowed roots"] * 2


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


def test_prompt_index_lists_model_invocable_skills_within_budget(tmp_path):
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
	without_read = build_system_prompt(
		SessionConfig(cwd=str(tmp_path), tools=["bash"]),
		skills=catalog.skills,
	)
	assert "<available_skills>" not in without_read

	many = tmp_path / "many"
	for index in range(MAX_SKILLS):
		_skill(many, f"skill-{index:03d}", description=f"Use for {index}. " + "x" * 1000)
	catalog = discover_skills(str(many), enabled=False, extra_paths=[str(many)])

	formatted = format_skills_for_prompt(catalog.skills)

	assert len(catalog.skills) == MAX_SKILLS
	assert len(formatted.encode("utf-8")) <= MAX_SKILL_INDEX_BYTES
	assert formatted.count("<skill>") < MAX_SKILLS


def test_skill_commands_expand_where_they_are_typed(tmp_path):
	_skill(tmp_path, "testing")
	_skill(tmp_path, "review", body="Review body")
	catalog = discover_skills(str(tmp_path), home=str(tmp_path / "none"), extra_paths=[str(tmp_path)])
	bodies = {"testing": "# Instructions\nRun the focused tests.", "review": "Review body"}
	typed = "please /skill:testing then /skill:review and /skill:testing"
	repeated = "/skill:testing  do /skill:testing"
	quoted = "/skill:testing fix it\n\n> try /skill:review or /skill:testing"
	cases = [
		# message, skills, instructions, command shown back
		(
			"/skill:testing\n\nAdd parser tests",
			["testing"],
			"Add parser tests",
			"/skill:testing Add parser tests",
		),
		(typed, ["testing", "review"], typed, typed),
		(
			"/skill:testing  fix it with /skill:review",
			["testing", "review"],
			"fix it with /skill:review",
			"/skill:testing fix it with /skill:review",
		),
		# named again later, the text stays as typed
		(repeated, ["testing"], repeated, repeated),
		(quoted, ["testing"], "fix it\n\n> try /skill:review or /skill:testing", quoted),
		("ordinary prompt", None, None, None),
		("what does this do?\n\n> Type /skill:testing to start", None, None, None),
		("use /skill:missing and /skill:testing.", None, None, None),
	]
	for message, names, instructions, command in cases:
		invocation = parse_skill_command(message, catalog.skills)
		if names is None:
			assert invocation is None, message
			continue
		assert invocation is not None, message
		assert [item.skill.name for item in invocation.skills] == names, message
		assert [item.content for item in invocation.skills] == [bodies[name] for name in names], message
		assert invocation.instructions == instructions, message
		text = format_skill_invocation(invocation)
		assert text.endswith(f"{bodies[names[-1]]}\n</skill>\n\n{instructions}"), message
		parsed = parse_skill_invocation(text)
		assert parsed is not None, message
		assert [skill.name for skill in parsed.skills] == names, message
		assert parsed.command == command, message

	looked_up = []
	assert (
		parse_skill_command(
			"why does /skill:missing fail? see a/skill:testing", catalog.skills, resolve=looked_up.append
		)
		is None
	)
	assert looked_up == ["missing"]


def test_skill_command_refusals(tmp_path):
	skills = tmp_path / "skills"
	_skill(skills, "testing")
	_skill(skills, "large", body="x" * 200_000)
	binary = tmp_path / "binary" / "SKILL.md"
	binary.parent.mkdir()
	binary.write_bytes(b"---\nname: binary\ndescription: Test things\n---\n" + b"x" * 20_000 + b"\xff")
	# an extra path may name a SKILL.md itself; discovery reads only its bounded frontmatter
	catalog = discover_skills(str(tmp_path), enabled=False, extra_paths=[str(skills), str(binary)])
	assert [skill.name for skill in catalog.skills] == ["binary", "large", "testing"]
	# what discovery recorded no longer resolves to the file about to be opened
	swapped = Skill(
		name="review",
		description="Use for tests.",
		path=str(_skill(tmp_path / "project", "review")),
		canonical_path=str(tmp_path / "elsewhere" / "SKILL.md"),
	)
	cases = [
		("/skill:missing and /skill:testing", None, "unknown skill: missing"),
		("/skill:binary", None, "UTF-8"),
		(f"/skill:large {'y' * 100_000}", None, "expanded skill exceeds"),
		("/skill:review", swapped, "skill path changed: review"),
	]
	for message, resolved, error in cases:
		with pytest.raises(SkillError, match=error):
			parse_skill_command(message, catalog.skills, resolve=lambda name: resolved)


class _GatedModel(Model):
	"""Holds its first turn until released; keeps a copy of every request."""

	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()
		self.requests = []

	async def run(self, request):
		self.requests.append(replace(request, messages=list(request.messages)))
		if len(self.requests) == 1:
			self.started.set()
			await self.release.wait()
		yield AssistantMessage(content="done")
		yield Usage()


async def test_a_skill_command_is_ordinary_user_text_when_steered_and_compacted(tmp_path):
	project = tmp_path / "project"
	project.mkdir()
	_skill(project / ".agents" / "skills", "testing")
	session = SessionStore(str(tmp_path / "data")).create(SessionConfig(cwd=str(project)))
	model = _GatedModel()

	first = await session.run("start", model=model)
	await model.started.wait()
	steering = await session.run("/skill:testing focus here")
	assert steering.status == "steered"
	model.release.set()
	assert first.task is not None
	await first.task

	assert len(model.requests) == 2
	assert any(
		isinstance(message, UserMessage) and parse_skill_invocation(message.text) is not None
		for message in model.requests[1].messages
	)
	message = [
		entry for row in session.log.read_since(0) if isinstance((entry := parse_event(row)), UserMessage)
	][-1]
	assert isinstance(message.content, str)
	assert '<skill name="testing"' in message.text
	assert message.text.endswith("focus here")
	parsed = parse_skill_invocation(message.text)
	assert parsed is not None
	assert [skill.name for skill in parsed.skills] == ["testing"]
	assert parsed.instructions == "focus here"

	compaction = await session.compact(model=model)
	assert compaction.task is not None
	await compaction.task

	summary_prompt = model.requests[-1].messages[0].text
	assert '<skill name="testing"' in summary_prompt
	assert "focus here" in summary_prompt


def test_a_session_keeps_its_catalog_private_and_reads_bodies_fresh(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	path = _skill(project / ".agents" / "skills", "testing", "Original description", body="Original body")
	data = str(tmp_path / "data")
	created = SessionStore(data).create(SessionConfig(cwd=str(project)))
	manifest = next((tmp_path / "data" / "sessions").rglob(f"{created.id}.skills.json"))
	assert json.loads(manifest.read_text())["skills"][0]["name"] == "testing"
	assert manifest.stat().st_mode & 0o777 == 0o600
	path.write_text(
		"---\nname: testing\ndescription: Changed later\n---\nUpdated body",
		encoding="utf-8",
	)

	reloaded = SessionStore(data).get(created.id)

	# the prompt and catalog stay as created; the body is read when the skill is used
	assert reloaded.config.system_prompt == created.config.system_prompt
	assert reloaded.skill_catalog.skills[0].description == "Original description"
	invocation = parse_skill_command("/skill:testing", reloaded.skill_catalog.skills)
	assert invocation is not None
	assert "Updated body" in format_skill_invocation(invocation)


def test_the_store_refuses_skills_outside_its_roots(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	outside_skill = _skill(tmp_path / "outside", "review")
	data = str(tmp_path / "data")
	store = SessionStore(data, allowed_roots=[str(project)])

	with pytest.raises(ValueError, match=r"skill path .* is not under an allowed root"):
		store.create(SessionConfig(cwd=str(project), skill_paths=[str(outside_skill.parent.parent)]))

	session = store.create(SessionConfig(cwd=str(project)))
	alias = project / ".agents" / "skills" / "review"
	alias.mkdir(parents=True)
	(alias / "SKILL.md").symlink_to(outside_skill)
	# linked in after create, it is still not invocable
	assert store.resolve_skill(session.config, "review") is None
	with pytest.raises(SkillError, match="unknown skill: review"):
		parse_skill_command(
			"/skill:review",
			session.skill_catalog.skills,
			resolve=lambda name: store.resolve_skill(session.config, name),
		)

	# a catalog stored without the fence is checked again by a fenced store
	unfenced = SessionStore(data, allowed_roots=[]).create(SessionConfig(cwd=str(project)))
	with pytest.raises(ValueError, match="stored skill 'review' is outside allowed roots"):
		SessionStore(data, allowed_roots=[str(project)]).get(unfenced.id)


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
	grep_result = await BUNDLED_TOOLS["grep"](pattern="reference", path=str(global_skills), ctx=ctx)
	assert "reference.txt:1:reference" in grep_result.content
	with pytest.raises(PermissionError):
		await BUILTIN_TOOLS["write"](path=str(global_skills / "changed.txt"), content="no", ctx=ctx)


def test_skills_over_the_api(tmp_path, monkeypatch):
	home = tmp_path / "home"
	project = tmp_path / "project"
	home.mkdir()
	project.mkdir()
	monkeypatch.setenv("HOME", str(home))
	_skill(project / ".agents" / "skills", "testing")
	data = tmp_path / "data"
	store = SessionStore(str(data), credential_store=CredentialStore(str(tmp_path / "credentials.json")))
	client = TestClient(create_app(store))
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
	# the title is the instructions typed after the command
	response = client.post(
		f"/sessions/{sid}/run?wait=true",
		json={"message": "/skill:testing add parser coverage"},
	)
	assert response.status_code == 200
	assert client.get(f"/sessions/{sid}").json()["title"] == "add parser coverage"

	# attachments stay beside the expanded text
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
	entry = [
		item
		for item in client.get(f"/sessions/{sid}/entries").json()["entries"]
		if item["type"] == "user_message"
	][-1]
	assert [block["type"] for block in entry["content"]] == ["text", "attachment"]
	assert "skill" not in entry
	parsed = parse_skill_invocation(entry["content"][0]["text"])
	assert parsed is not None
	assert [skill.name for skill in parsed.skills] == ["testing"]
	assert parsed.instructions == "inspect this"

	# a skill added after create is listed and invocable
	_skill(project / ".agents" / "skills", "review", "Added later")
	listed = client.get(f"/sessions/{sid}/skills").json()["skills"]
	response = client.post(f"/sessions/{sid}/run?wait=true", json={"message": "/skill:review"})
	assert response.status_code == 200
	assert [skill["name"] for skill in listed] == ["review", "testing"]
	# invoking adopts it, so its directory keeps its read root across a restart
	assert [skill.name for skill in SessionStore(str(data)).get(sid).skill_catalog.skills] == [
		"review",
		"testing",
	]
	# the prompt the model sees was composed once and does not gain the new skill
	assert "Added later" not in store.get(sid).config.system_prompt
