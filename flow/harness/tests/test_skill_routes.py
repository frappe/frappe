"""Skill file management routes and the policy-capped tool list."""

import os

from fastapi.testclient import TestClient

from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.policy import DEPLOYED
from flow_harness.session import skills as skills_module
from flow_harness.session.store import SessionStore

SKILL = "---\nname: {name}\ndescription: Use for tests.\n---\n\n# Steps\nRun the tests.\n"


def _client(tmp_path, monkeypatch, *, policy=None, auth=None, **store_kw):
	home = tmp_path / "home"
	home.mkdir(parents=True)
	monkeypatch.setenv("HOME", str(home))
	store_kw.setdefault("credential_store", CredentialStore(str(tmp_path / "credentials.json")))
	app = create_app(SessionStore(str(tmp_path / "data"), **store_kw), policy=policy, auth_token=auth)
	headers = {"Authorization": f"Bearer {auth}"} if auth else None
	return TestClient(app, headers=headers), home


def _write(root, name, content=None):
	directory = root / name
	directory.mkdir(parents=True)
	(directory / "SKILL.md").write_text(content or SKILL.format(name=name), encoding="utf-8")
	return directory / "SKILL.md"


def test_lists_global_and_project_skills_with_errors(tmp_path, monkeypatch):
	c, home = _client(tmp_path, monkeypatch)
	project = tmp_path / "project"
	project.mkdir()
	_write(home / ".agents" / "skills", "review")
	_write(project / ".agents" / "skills", "deploy")
	_write(project / ".agents" / "skills", "broken", "no frontmatter\n")

	data = c.get("/skills", params={"cwd": str(project)}).json()
	assert data["roots"]["global"] == os.path.realpath(str(home / ".agents" / "skills"))
	assert data["roots"]["project"] == os.path.realpath(str(project / ".agents" / "skills"))
	rows = {(row["scope"], row["name"]): row for row in data["skills"]}
	assert rows[("global", "review")]["description"] == "Use for tests."
	assert rows[("project", "deploy")]["error"] is None
	assert rows[("project", "broken")]["error"] == "skill requires YAML frontmatter"

	# no cwd: only the global root is listed
	assert [row["scope"] for row in c.get("/skills").json()["skills"]] == ["global"]

	# a scope cut off by the scan cap is reported
	monkeypatch.setattr(skills_module, "MAX_SKILL_DIRECTORY_ENTRIES", 1)
	data = c.get("/skills", params={"cwd": str(project)}).json()
	assert len(data["skills"]) == 2
	assert data["truncated"] == ["project"]


def test_write_read_delete_roundtrip(tmp_path, monkeypatch):
	c, home = _client(tmp_path, monkeypatch)
	path = str(home / ".agents" / "skills" / "notes" / "SKILL.md")

	assert c.put("/skills/file", json={"path": path, "content": SKILL.format(name="notes")}).json() == {
		"path": path
	}
	assert c.get("/skills/file", params={"path": path}).json()["content"] == SKILL.format(name="notes")

	# invalid content is refused with the loader's reason, and the file keeps its old text
	rejected = c.put("/skills/file", json={"path": path, "content": "---\nname: other\n---\n"})
	assert rejected.status_code == 400
	assert rejected.json()["detail"] == "skill name 'other' must match parent directory 'notes'"
	assert c.get("/skills/file", params={"path": path}).json()["content"] == SKILL.format(name="notes")
	assert (
		c.put("/skills/file", json={"path": path, "content": "no frontmatter"}).json()["detail"]
		== "skill requires YAML frontmatter"
	)

	assert c.delete("/skills/file", params={"path": path}).json() == {"status": "deleted"}
	assert not os.path.exists(os.path.dirname(path))  # the emptied directory goes too
	assert c.delete("/skills/file", params={"path": path}).status_code == 404


def test_only_skill_files_under_a_root_are_managed(tmp_path, monkeypatch):
	c, home = _client(tmp_path, monkeypatch)
	root = home / ".agents" / "skills"
	body = {"content": "x"}
	for path in (
		str(tmp_path / "elsewhere" / "notes" / "SKILL.md"),  # outside every root
		str(root / "notes" / "README.md"),  # not a SKILL.md
		str(root / "Bad Name" / "SKILL.md"),  # invalid skill name
		str(root / "SKILL.md"),  # the root itself
		str(root / "deep" / "nested" / "SKILL.md"),  # not a direct child
	):
		assert c.put("/skills/file", json={"path": path, **body}).status_code == 400, path
		assert c.get("/skills/file", params={"path": path}).status_code == 400, path
	assert (
		c.put(
			"/skills/file", json={"path": str(root / "ok" / "SKILL.md"), "content": "x" * (256 * 1024 + 1)}
		).status_code
		== 413
	)


def test_skill_paths_follow_symlinks_but_obey_the_fence(tmp_path, monkeypatch):
	c, home = _client(tmp_path, monkeypatch)
	target = _write(tmp_path / "elsewhere", "linked")  # e.g. a skill shared from another harness
	root = home / ".agents" / "skills"
	root.mkdir(parents=True)
	(root / "linked").symlink_to(target.parent)
	path = str(root / "linked" / "SKILL.md")

	assert [row["name"] for row in c.get("/skills").json()["skills"]] == ["linked"]
	assert c.get("/skills/file", params={"path": path}).json()["content"] == SKILL.format(name="linked")
	c.put("/skills/file", json={"path": path, "content": SKILL.format(name="linked") + "More.\n"})
	assert target.read_text().endswith("More.\n")

	# a fenced daemon refuses a link whose target is outside every allowed root,
	# and a project root outside them
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	fenced, home = _client(tmp_path / "fenced", monkeypatch, allowed_roots=[str(allowed)])
	root = home / ".agents" / "skills"
	root.mkdir(parents=True)
	(root / "linked").symlink_to(target.parent)
	assert fenced.get("/skills/file", params={"path": str(root / "linked" / "SKILL.md")}).status_code == 400
	assert fenced.get("/skills", params={"cwd": str(allowed)}).status_code == 200
	assert fenced.get("/skills", params={"cwd": str(tmp_path / "other")}).status_code == 400


def test_deployed_policy_disables_skill_management_the_tool_list_and_settings(tmp_path, monkeypatch):
	c, _ = _client(tmp_path, monkeypatch, policy=DEPLOYED, auth="t", tool_allowlist=DEPLOYED.tool_allowlist)
	assert c.get("/skills").status_code == 403
	assert c.put("/skills/file", json={"path": "/x/y/SKILL.md", "content": ""}).status_code == 403
	assert c.get("/tools").status_code == 403
	assert c.get("/settings").status_code == 403
	assert c.patch("/settings", json={"settings": {"theme": "dark"}}).status_code == 403


def test_tools_list_every_builtin_up_to_the_allowlist(tmp_path, monkeypatch):
	c, _ = _client(tmp_path, monkeypatch)
	tools = c.get("/tools").json()["tools"]
	assert [t["name"] for t in tools if t["extension"] is None] == [
		"bash",
		"read",
		"write",
		"edit",
		"subagent",
		"grep",
		"suggest_replies",
	]
	assert all(t["description"] for t in tools)

	capped, _ = _client(tmp_path / "capped", monkeypatch, tool_allowlist={"read", "grep"})
	assert [t["name"] for t in capped.get("/tools").json()["tools"]] == ["read", "grep"]
