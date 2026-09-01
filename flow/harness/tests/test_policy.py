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


def _deployed_client(tmp_path, **store_kw) -> TestClient:
	store_kw.setdefault("tool_allowlist", DEPLOYED.tool_allowlist)
	store_kw.setdefault("callback_hosts", DEPLOYED.callback_hosts)
	app = create_app(_store(tmp_path, **store_kw), policy=DEPLOYED, auth_token="test-token")
	return TestClient(app, headers={"Authorization": "Bearer test-token"})


def test_resolve_policy_profiles():
	assert resolve_policy("local") == ServerPolicy()
	deployed = resolve_policy("deployed")
	assert deployed.tool_allowlist == frozenset({"read_file", "grep"})
	assert deployed.require_auth
	assert deployed.callback_hosts == frozenset()
	assert not deployed.fs_api
	assert not deployed.providers_api
	assert not deployed.extensions_api
	assert not deployed.skills_api
	with pytest.raises(ValueError, match="unknown profile"):
		resolve_policy("production")


def test_resolve_policy_fills_callback_hosts_for_deployed_only():
	deployed = resolve_policy("deployed", callback_hosts=["site.localhost:8000"])
	assert deployed.callback_hosts == frozenset({"site.localhost:8000"})
	assert resolve_policy("local", callback_hosts=["site.localhost:8000"]).callback_hosts is None


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
	capped = _store(tmp_path / "capped", extension_paths=[str(extension)], tool_allowlist=["read_file"])
	session = capped.create(SessionConfig(cwd=str(tmp_path)))
	assert set(session.server_tools) == {"read_file"}


def test_allowlist_filters_stored_session_on_load(tmp_path):
	sid = _store(tmp_path).create(SessionConfig(cwd=str(tmp_path))).id
	reopened = _store(tmp_path, tool_allowlist=DEPLOYED.tool_allowlist)
	assert set(reopened.get(sid).server_tools) == {"read_file", "grep"}


def test_callback_url_fenced_to_allowed_hosts(tmp_path):
	c = _client(tmp_path, callback_hosts=["site.localhost:8000"])

	def create(url: str):
		return c.post("/sessions", json={"cwd": str(tmp_path), "callback_url": url})

	assert create("http://site.localhost:8000/api/method/tool_callback").status_code == 200
	for url in (
		"http://site.localhost:9000/cb",  # wrong port
		"http://169.254.169.254/latest/meta-data",  # internal service
		"ftp://site.localhost:8000/cb",  # wrong scheme
	):
		response = create(url)
		assert response.status_code == 400
		assert "callback_url" in response.json()["detail"]


def test_deployed_refuses_callbacks_without_configured_hosts(tmp_path):
	c = _deployed_client(tmp_path)
	r = c.post("/sessions", json={"cwd": str(tmp_path), "callback_url": "http://localhost:8000/cb"})
	assert r.status_code == 400
	assert "callback_url" in r.json()["detail"]


def test_callback_url_checked_when_loading_stored_session(tmp_path):
	session_config = SessionConfig(cwd=str(tmp_path), callback_url="http://internal:9000/steal")
	sid = _store(tmp_path).create(session_config).id
	reopened = _store(tmp_path, callback_hosts=frozenset())
	with pytest.raises(ValueError, match="callback_url"):
		reopened.get(sid)


def test_create_app_refuses_deployed_without_token(tmp_path):
	with pytest.raises(ValueError, match="requires auth"):
		create_app(_store(tmp_path), policy=DEPLOYED)


def test_serve_refuses_deployed_without_token(tmp_path, monkeypatch):
	import importlib
	from argparse import Namespace

	from flow import config
	from flow.model.auth import AuthError

	cli_main = importlib.import_module("flow.cli.main")

	monkeypatch.setattr(config, "AUTH_TOKEN", None)
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	monkeypatch.setattr(config, "TENANTS_FILE", None)
	args = Namespace(
		host="127.0.0.1",
		port=0,
		data_dir=str(tmp_path),
		profile="deployed",
		background=False,
		uds=None,
		parent_watch=False,
		extension=[],
		no_extensions=False,
	)
	with pytest.raises(AuthError, match="FLOW_AUTH_TOKEN"):
		cli_main._serve(args)
