"""Deployed guardrails: the request size cap, audit log, and the extension-loading
wire-up of `flow serve`."""

import json
import os

from fastapi.testclient import TestClient

from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.policy import DEPLOYED, ServerPolicy
from flow_harness.server.request_limits import REFUSAL
from flow_harness.server.tenants import TenantTemplate
from flow_harness.session.store import SessionStore


def _store(tmp_path, **store_kw) -> SessionStore:
	store_kw.setdefault("credential_store", CredentialStore(str(tmp_path / "credentials.json")))
	return SessionStore(str(tmp_path / "data"), **store_kw)


def test_request_size_cap(tmp_path):
	capped = TestClient(create_app(_store(tmp_path), policy=ServerPolicy(max_request_bytes=2048)))
	assert capped.post("/sessions", json={"cwd": str(tmp_path)}).status_code == 200
	big = {"cwd": str(tmp_path), "system_suffix": "x" * 4096}
	response = capped.post("/sessions", json=big)
	assert response.status_code == 413
	assert response.json()["detail"] == REFUSAL
	assert capped.get("/sessions").status_code == 200
	# the local default stays uncapped
	open_client = TestClient(create_app(_store(tmp_path / "open")))
	assert open_client.post("/sessions", json=big).status_code == 200


def test_audit_log_records_sensitive_calls_and_their_site(tmp_path):
	store = _store(tmp_path)
	app = create_app(store, auth_token="secret", policy=ServerPolicy(audit_log=True))
	client = TestClient(app, headers={"Authorization": "Bearer secret"})
	sid = client.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	assert client.get("/sessions").status_code == 200  # reads are not audited
	assert client.delete(f"/sessions/{sid}").status_code == 200
	intruder = TestClient(app, headers={"Authorization": "Bearer wrong"})
	assert intruder.post("/sessions", json={"cwd": str(tmp_path)}).status_code == 401

	path = os.path.join(store.data_dir, "audit.jsonl")
	assert os.stat(path).st_mode & 0o777 == 0o600
	rows = [json.loads(line) for line in open(path, encoding="utf-8")]
	assert [(row["method"], row["path"], row["status"]) for row in rows] == [
		("POST", "/sessions", 200),
		("DELETE", f"/sessions/{sid}", 200),
		("POST", "/sessions", 401),
	]
	assert all(isinstance(row["ts"], float) and "site" not in row for row in rows)

	# a tenant's calls name its site
	site_root = tmp_path / "sites" / "alpha"
	site_root.mkdir(parents=True)
	(site_root / "site.json").write_text('{"token": "alpha-token"}')
	store = _store(tmp_path / "tenant")
	tenants = TenantTemplate(
		token_file=str(tmp_path / "sites" / "{site}" / "site.json"),
		token_key="token",
		allowed_roots=(str(tmp_path / "sites" / "{site}"),),
	)
	app = create_app(store, tenants=tenants, policy=ServerPolicy(audit_log=True))
	client = TestClient(app, headers={"Authorization": "Bearer alpha-token", "X-Flow-Site": "alpha"})
	assert client.post("/sessions", json={"cwd": str(site_root)}).status_code == 200
	rows = [json.loads(line) for line in open(os.path.join(store.data_dir, "audit.jsonl"))]
	assert rows[0]["site"] == "alpha"


def test_serve_wires_policy_into_the_store(tmp_path, monkeypatch):
	import importlib
	from argparse import Namespace

	from flow_harness import config

	cli_main = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "AUTH_TOKEN", "tok")
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	monkeypatch.setattr(config, "TENANTS", None)
	monkeypatch.setattr(config, "REDIS_URL", None)
	monkeypatch.setattr(config, "CALLBACK_HOSTS", [])
	monkeypatch.setattr(config, "POLICY", None)
	monkeypatch.setattr(config, "EXTENSIONS_PATH", str(tmp_path / "no-extensions"))
	monkeypatch.setattr(cli_main, "_warm_litellm", lambda: None)
	monkeypatch.setattr(cli_main, "_run_server", lambda *args, **kwargs: None)

	captured: dict = {}

	def capturing_store(data_dir, **kwargs):
		captured.clear()
		captured.update(kwargs)
		return SessionStore(
			data_dir, credential_store=CredentialStore(str(tmp_path / "credentials.json")), **kwargs
		)

	monkeypatch.setattr("flow_harness.session.store.SessionStore", capturing_store)

	def serve(profile: str) -> dict:
		cli_main._serve(
			Namespace(
				host="127.0.0.1",
				port=0,
				data_dir=str(tmp_path / profile),
				profile=profile,
				background=False,
				uds=None,
				parent_watch=False,
				extension=[],
				no_extensions=False,
			)
		)
		return dict(captured)

	deployed = serve("deployed")
	assert deployed["extensions_enabled"] is False
	assert deployed["tool_allowlist"] == DEPLOYED.tool_allowlist
	local = serve("local")
	assert local["extensions_enabled"] is True
	monkeypatch.setattr(config, "POLICY", '{"tool_allowlist": ["read"]}')
	overridden = serve("deployed")
	assert overridden["tool_allowlist"] == frozenset({"read"})


def test_spawn_private_scrubs_daemon_env(tmp_path, monkeypatch):
	"""Stray FLOW_POLICY/FLOW_TENANTS in the shell must not reach the TUI's own
	daemon — a tenants template would even refuse startup beside the injected token."""
	from flow_harness.cli import daemon as cli_daemon

	captured: dict = {}

	def fake_popen(argv, **kwargs):
		captured["env"] = kwargs["env"]
		return object()

	monkeypatch.setenv("FLOW_POLICY", '{"skills_api": false}')
	monkeypatch.setenv("FLOW_TENANTS", '{"token_file": "/s/{site}/t.json", "allowed_roots": ["/s"]}')
	monkeypatch.setattr(cli_daemon.subprocess, "Popen", fake_popen)
	monkeypatch.setattr(cli_daemon, "_wait_healthz", lambda *args, **kwargs: None)
	spawned = cli_daemon.spawn_private(str(tmp_path))
	assert "FLOW_POLICY" not in captured["env"]
	assert "FLOW_TENANTS" not in captured["env"]
	assert captured["env"]["FLOW_AUTH_TOKEN"] == spawned.token
