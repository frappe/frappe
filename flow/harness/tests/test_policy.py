"""Server policy: profile resolution, the tool cap, and gated route groups."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flow.model.credentials import CredentialStore
from flow.server import create_app
from flow.server.policy import DEPLOYED, ServerPolicy, resolve_policy
from flow.session.config import SessionConfig
from flow.session.store import SessionStore

HELLO_EXTENSION = """
from flow.tools import ToolResult, tool

@tool()
async def hello(who: str = "world", *, ctx):
    return ToolResult(content=f"Hello, {who}!")

def setup(flow):
    flow.register_tool(hello)
"""


def _store(tmp_path, **store_kw) -> SessionStore:
	store_kw.setdefault("credential_store", CredentialStore(str(tmp_path / "credentials.json")))
	return SessionStore(str(tmp_path / "data"), **store_kw)


def _client(tmp_path, policy: ServerPolicy | None = None, **store_kw) -> TestClient:
	return TestClient(create_app(_store(tmp_path, **store_kw), policy=policy))


def _deployed_client(tmp_path) -> TestClient:
	return _client(tmp_path, policy=DEPLOYED, tool_allowlist=DEPLOYED.tool_allowlist)


def test_resolve_policy_profiles():
	assert resolve_policy("local") == ServerPolicy()
	deployed = resolve_policy("deployed")
	assert deployed.tool_allowlist == frozenset({"read_file", "grep"})
	assert not deployed.fs_api
	assert not deployed.providers_api
	assert not deployed.extensions_api
	assert not deployed.skills_api
	with pytest.raises(ValueError, match="unknown profile"):
		resolve_policy("production")


def test_deployed_rejects_explicit_tools_outside_cap(tmp_path):
	c = _deployed_client(tmp_path)
	r = c.post("/sessions", json={"cwd": str(tmp_path), "tools": ["bash"]})
	assert r.status_code == 400
	assert "bash" in r.json()["detail"]
	r = c.post("/sessions", json={"cwd": str(tmp_path), "tools": ["read_file", "write", "edit"]})
	assert r.status_code == 400
	assert "edit, write" in r.json()["detail"]


def test_deployed_clamps_defaulted_tools(tmp_path):
	c = _deployed_client(tmp_path)
	r = c.post("/sessions", json={"cwd": str(tmp_path)})
	assert r.status_code == 200
	assert r.json()["config"]["tools"] == ["read_file", "grep"]


def test_deployed_allows_capped_subset(tmp_path):
	c = _deployed_client(tmp_path)
	r = c.post("/sessions", json={"cwd": str(tmp_path), "tools": ["grep"]})
	assert r.status_code == 200
	assert r.json()["config"]["tools"] == ["grep"]


def test_deployed_route_gates(tmp_path):
	c = _deployed_client(tmp_path)
	target = {"cwd": str(tmp_path), "path": "notes.txt", "content": "hi"}
	assert c.put("/fs/file", json=target).status_code == 403
	assert not (tmp_path / "notes.txt").exists()
	assert c.post("/fs/pick").status_code == 403
	assert c.get("/fs/files", params={"cwd": str(tmp_path)}).status_code == 403
	assert c.get("/fs/file", params={"cwd": str(tmp_path), "path": "x"}).status_code == 403
	assert c.get("/fs/git/changes", params={"cwd": str(tmp_path)}).status_code == 403
	assert c.get("/models").status_code == 403
	assert c.post("/providers/anthropic/api-key", json={"key": "sk-x"}).status_code == 403
	assert c.post("/extensions/reload").status_code == 403
	assert c.get("/sessions/any/extensions").status_code == 403
	assert c.post("/skills", json={"cwd": str(tmp_path)}).status_code == 403
	assert c.get("/sessions/any/skills").status_code == 403
	assert c.get("/sessions/any/file/diff", params={"path": "x"}).status_code == 403


def test_local_defaults_keep_everything_on(tmp_path):
	c = _client(tmp_path)
	r = c.put("/fs/file", json={"cwd": str(tmp_path), "path": "notes.txt", "content": "hi"})
	assert r.status_code == 200
	assert (tmp_path / "notes.txt").read_text() == "hi"
	assert c.get("/fs/files", params={"cwd": str(tmp_path)}).status_code == 200
	assert c.post("/extensions/reload").status_code == 200
	assert c.post("/skills", json={"cwd": str(tmp_path)}).status_code == 200
	r = c.post("/sessions", json={"cwd": str(tmp_path), "tools": ["bash"]})
	assert r.status_code == 200
	assert r.json()["config"]["tools"] == ["bash"]


def _write_extension(directory: Path, name: str, body: str) -> Path:
	directory.mkdir(parents=True, exist_ok=True)
	path = directory / f"{name}.py"
	path.write_text(body)
	return path


def test_allowlist_caps_extension_tools(tmp_path):
	extension = _write_extension(tmp_path / "ext", "hello", HELLO_EXTENSION)
	open_store = _store(tmp_path / "open", extension_paths=[str(extension)])
	assert "hello" in open_store.create(SessionConfig(cwd=str(tmp_path))).server_tools
	capped = _store(
		tmp_path / "capped", extension_paths=[str(extension)], tool_allowlist=["read_file"]
	)
	session = capped.create(SessionConfig(cwd=str(tmp_path)))
	assert set(session.server_tools) == {"read_file"}


def test_allowlist_filters_stored_session_on_load(tmp_path):
	sid = _store(tmp_path).create(SessionConfig(cwd=str(tmp_path))).id
	reopened = _store(tmp_path, tool_allowlist=DEPLOYED.tool_allowlist)
	assert set(reopened.get(sid).server_tools) == {"read_file", "grep"}
