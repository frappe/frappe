"""Server policy: profile resolution, the tool cap, and gated route groups."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.policy import DEPLOYED, ServerPolicy, resolve_policy
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import PolicyError, SessionStore

HELLO_EXTENSION = """
from flow_harness.tools import ToolResult, tool

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
	assert deployed.tool_allowlist == frozenset({"read", "grep"})
	assert deployed.require_auth
	assert deployed.inline_credentials
	assert deployed.callback_hosts == frozenset()
	assert not deployed.extensions
	assert deployed.max_request_bytes == 224 * 1024 * 1024
	assert deployed.audit_log
	assert not deployed.fs_api
	assert not deployed.providers_api
	assert not deployed.skills_api
	assert not deployed.tools_api
	assert not deployed.settings_api
	assert not deployed.workspaces_api
	with pytest.raises(ValueError, match="unknown profile"):
		resolve_policy("production")
	# configured callback hosts fill the deployed profile only
	deployed = resolve_policy("deployed", callback_hosts=["site.localhost:8000"])
	assert deployed.callback_hosts == frozenset({"site.localhost:8000"})
	assert resolve_policy("local", callback_hosts=["site.localhost:8000"]).callback_hosts is None


def test_policy_overrides_adjust_switches_but_never_weaken_auth_or_audit():
	overrides = '{"skills_api": true, "tool_allowlist": ["read", "grep", "bash"], "max_request_bytes": null}'
	policy = resolve_policy("deployed", overrides=overrides)
	assert policy.skills_api
	assert policy.tool_allowlist == frozenset({"read", "grep", "bash"})
	assert policy.max_request_bytes is None
	assert policy.require_auth and not policy.fs_api  # untouched switches keep the profile
	hardened = resolve_policy("local", overrides='{"require_auth": true, "extensions": false}')
	assert hardened.require_auth
	assert not hardened.extensions
	# hardening local on stays allowed; false-on-false is a no-op, not an error
	hardened = resolve_policy("local", overrides='{"require_auth": true, "audit_log": true}')
	assert hardened.require_auth and hardened.audit_log
	assert resolve_policy("local", overrides='{"audit_log": false}').audit_log is False
	# overrides win over the callback hosts env
	policy = resolve_policy(
		"deployed", callback_hosts=["a.local:1"], overrides='{"callback_hosts": ["b.local:2"]}'
	)
	assert policy.callback_hosts == frozenset({"b.local:2"})

	# turning auth or audit off, and malformed input, are refused
	for overrides, error in (
		('{"require_auth": false}', "cannot turn off require_auth"),
		('{"audit_log": false}', "cannot turn off audit_log"),
		("not json", "FLOW_POLICY"),
		('["skills_api"]', "FLOW_POLICY"),
		('{"profile": "local"}', "FLOW_POLICY"),
		('{"nope": true}', "FLOW_POLICY"),
		('{"skills_api": "yes"}', "FLOW_POLICY"),
		('{"tool_allowlist": "bash"}', "FLOW_POLICY"),
		('{"max_request_bytes": -5}', "FLOW_POLICY"),
		('{"max_request_bytes": true}', "FLOW_POLICY"),
	):
		with pytest.raises(ValueError, match=error):
			resolve_policy("deployed", overrides=overrides)


def _write_extension(directory: Path, name: str, body: str) -> Path:
	directory.mkdir(parents=True, exist_ok=True)
	path = directory / f"{name}.py"
	path.write_text(body)
	return path


def test_tool_allowlist_caps_builtin_extension_and_stored_session_tools(tmp_path):
	c = _deployed_client(tmp_path)
	cases = [
		# requested tools, status, the names refused or the tools kept
		(["bash"], 400, "bash"),
		(["read", "write", "edit"], 400, "edit, write"),
		(["grep"], 200, ["grep"]),
		(None, 200, ["read"]),  # the defaulted list is clamped, not refused
	]
	for tools, status, expected in cases:
		body = {"cwd": str(tmp_path)} if tools is None else {"cwd": str(tmp_path), "tools": tools}
		r = c.post("/sessions", json=body)
		assert r.status_code == status, tools
		if status == 400:
			assert expected in r.json()["detail"], tools
		else:
			assert r.json()["config"]["tools"] == expected, tools

	extension = _write_extension(tmp_path / "ext", "hello", HELLO_EXTENSION)
	open_store = _store(tmp_path / "open", extension_paths=[str(extension)])
	assert "hello" in open_store.create(SessionConfig(cwd=str(tmp_path))).server_tools
	capped = _store(tmp_path / "capped", extension_paths=[str(extension)], tool_allowlist=["read"])
	# left unsent, the list is clamped rather than refused, like the built-in default
	assert set(capped.create(SessionConfig(cwd=str(tmp_path))).server_tools) == {"read"}
	with pytest.raises(PolicyError, match="hello"):
		capped.create(SessionConfig(cwd=str(tmp_path), extension_tools=["hello"]))

	# a session stored before the cap loads filtered
	sid = _store(tmp_path / "stored").create(SessionConfig(cwd=str(tmp_path))).id
	reopened = _store(tmp_path / "stored", tool_allowlist=DEPLOYED.tool_allowlist)
	assert set(reopened.get(sid).server_tools) == {"read"}


def test_deployed_gates_route_groups_that_local_keeps_on(tmp_path):
	c = _deployed_client(tmp_path / "deployed")
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
	assert c.get("/workspaces").status_code == 403

	c = _client(tmp_path / "local")
	r = c.put("/fs/file", json=target)
	assert r.status_code == 200
	assert (tmp_path / "notes.txt").read_text() == "hi"
	assert c.get("/fs/files", params={"cwd": str(tmp_path)}).status_code == 200
	assert c.post("/extensions/reload").status_code == 200
	assert c.post("/skills", json={"cwd": str(tmp_path)}).status_code == 200
	assert c.get("/workspaces").status_code == 200
	r = c.post("/sessions", json={"cwd": str(tmp_path), "tools": ["bash"]})
	assert r.status_code == 200
	assert r.json()["config"]["tools"] == ["bash"]


def test_callback_url_fenced_to_allowed_hosts(tmp_path):
	c = _client(tmp_path, callback_hosts=["site.localhost:8000"])

	def create(client, url: str):
		return client.post("/sessions", json={"cwd": str(tmp_path), "callback_url": url})

	assert create(c, "http://site.localhost:8000/api/method/tool_callback").status_code == 200
	for client, url in (
		(c, "http://site.localhost:9000/cb"),  # wrong port
		(c, "http://169.254.169.254/latest/meta-data"),  # internal service
		(c, "ftp://site.localhost:8000/cb"),  # wrong scheme
		(_deployed_client(tmp_path), "http://localhost:8000/cb"),  # deployed without configured hosts
	):
		response = create(client, url)
		assert response.status_code == 400, url
		assert "callback_url" in response.json()["detail"], url

	# a stored session behind a tightened fence is refused when it loads
	session_config = SessionConfig(cwd=str(tmp_path), callback_url="http://internal:9000/steal")
	sid = _store(tmp_path).create(session_config).id
	with pytest.raises(PolicyError, match="callback_url"):
		_store(tmp_path, callback_hosts=frozenset()).get(sid)
	response = _client(tmp_path, callback_hosts=frozenset()).get(f"/sessions/{sid}")
	assert response.status_code == 400
	assert "callback_url" in response.json()["detail"]


def test_deployed_refuses_to_start_without_a_token(tmp_path, monkeypatch):
	import importlib
	from argparse import Namespace

	from flow_harness import config
	from flow_harness.model.auth import AuthError

	with pytest.raises(ValueError, match="requires auth"):
		create_app(_store(tmp_path), policy=DEPLOYED)

	cli_main = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "AUTH_TOKEN", None)
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	monkeypatch.setattr(config, "TENANTS", None)
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
