"""Multi-tenant mode: the tenants file, per-site auth, and per-site isolation."""

import importlib
import json
from argparse import Namespace

import pytest
from fastapi.testclient import TestClient

from flow.cli.daemon import DaemonError
from flow.model.credentials import CredentialStore
from flow.server import create_app
from flow.server.policy import DEPLOYED
from flow.server.tenants import Tenant, load_tenants
from flow.session.store import SessionStore

TENANTS = [
	Tenant(site="site1.localhost", token="token-one"),
	Tenant(site="site2.localhost", token="token-two"),
]


def _store(tmp_path, **store_kw) -> SessionStore:
	store_kw.setdefault("credential_store", CredentialStore(str(tmp_path / "credentials.json")))
	return SessionStore(str(tmp_path / "data"), **store_kw)


def _auth(token: str) -> dict[str, str]:
	return {"Authorization": f"Bearer {token}"}


def test_load_tenants_parses_sites_tokens_and_roots(tmp_path):
	path = tmp_path / "tenants.json"
	path.write_text(
		json.dumps(
			{
				"site1.localhost": {"token": "abc", "allowed_roots": ["/srv/site1"]},
				"site2.localhost": {"token": "def", "allowed_roots": ["/srv/site2"]},
			}
		)
	)
	tenants = load_tenants(str(path))
	assert tenants == [
		Tenant(site="site1.localhost", token="abc", allowed_roots=("/srv/site1",)),
		Tenant(site="site2.localhost", token="def", allowed_roots=("/srv/site2",)),
	]


def test_load_tenants_rejects_broken_files(tmp_path):
	cases = [
		("[]", "non-empty JSON object"),
		("{}", "non-empty JSON object"),
		('{"site1": "just-a-token"}', "must be a JSON object"),
		('{"site1": {}}', "token must be a non-empty string"),
		('{"site1": {"token": "  "}}', "token must be a non-empty string"),
		('{"site1": {"token": "a"}}', "allowed_roots is required"),
		('{"site1": {"token": "a", "alowed_roots": ["/x"]}}', "unknown keys: alowed_roots"),
		('{"site1": {"token": "a", "allowed_roots": []}}', "non-empty list of paths"),
		('{"site1": {"token": "a", "allowed_roots": ["/x", 3]}}', "non-empty list of paths"),
		(
			'{"site1": {"token": "same", "allowed_roots": ["/x"]},'
			' "site2": {"token": "same", "allowed_roots": ["/x"]}}',
			"reuses another site's token",
		),
	]
	path = tmp_path / "tenants.json"
	for content, match in cases:
		path.write_text(content)
		with pytest.raises(ValueError, match=match):
			load_tenants(str(path))


def test_for_site_partitions_and_shares(tmp_path):
	store = _store(tmp_path)
	site = store.for_site("site1.localhost")
	assert site.sessions_dir == str(tmp_path / "data" / "tenants" / "site1.localhost" / "sessions")
	assert site.credential_store is store.credential_store
	other = store.for_site("site2.localhost")
	assert other.sessions_dir != site.sessions_dir


def test_for_site_rejects_unsafe_names(tmp_path):
	store = _store(tmp_path)
	for name in ("..", ".", "a/b", "../escape", ".hidden", ""):
		with pytest.raises(ValueError, match="invalid site name"):
			store.for_site(name)


def test_sites_only_see_their_own_sessions(tmp_path):
	c = TestClient(create_app(_store(tmp_path), tenants=TENANTS))
	r = c.post("/sessions", json={"cwd": str(tmp_path)}, headers=_auth("token-one"))
	assert r.status_code == 200
	sid = r.json()["session_id"]
	assert c.get(f"/sessions/{sid}", headers=_auth("token-one")).status_code == 200
	sessions = c.get("/sessions", headers=_auth("token-two")).json()["sessions"]
	assert sessions == []
	assert c.get(f"/sessions/{sid}", headers=_auth("token-two")).status_code == 404
	assert c.get(f"/sessions/{sid}/entries", headers=_auth("token-two")).status_code == 404
	assert c.delete(f"/sessions/{sid}", headers=_auth("token-two")).status_code == 404
	assert c.get("/sessions").status_code == 401
	assert c.get("/sessions", headers=_auth("wrong")).status_code == 401
	assert c.get("/healthz").status_code == 200


def test_same_session_id_allowed_on_two_sites(tmp_path):
	c = TestClient(create_app(_store(tmp_path), tenants=TENANTS))
	body = {"cwd": str(tmp_path), "session_id": "shared-id"}
	assert c.post("/sessions", json=body, headers=_auth("token-one")).status_code == 200
	assert c.post("/sessions", json=body, headers=_auth("token-two")).status_code == 200


def test_per_site_allowed_roots(tmp_path):
	fenced = tmp_path / "site1"
	shared = tmp_path / "shared"
	fenced.mkdir()
	shared.mkdir()
	tenants = [
		Tenant(site="site1.localhost", token="token-one", allowed_roots=(str(fenced),)),
		Tenant(site="site2.localhost", token="token-two"),
	]
	store = _store(tmp_path, allowed_roots=[str(shared)])
	c = TestClient(create_app(store, tenants=tenants))
	assert c.post("/sessions", json={"cwd": str(fenced)}, headers=_auth("token-one")).status_code == 200
	r = c.post("/sessions", json={"cwd": str(shared)}, headers=_auth("token-one"))
	assert r.status_code == 400
	assert "allowed root" in r.json()["detail"]
	# no roots of its own: site2 inherits the daemon-wide fence
	assert c.post("/sessions", json={"cwd": str(shared)}, headers=_auth("token-two")).status_code == 200
	assert c.post("/sessions", json={"cwd": str(fenced)}, headers=_auth("token-two")).status_code == 400


def test_tenants_satisfy_deployed_auth(tmp_path):
	store = _store(tmp_path, tool_allowlist=DEPLOYED.tool_allowlist, callback_hosts=DEPLOYED.callback_hosts)
	c = TestClient(create_app(store, policy=DEPLOYED, tenants=TENANTS))
	r = c.post("/sessions", json={"cwd": str(tmp_path)}, headers=_auth("token-one"))
	assert r.status_code == 200
	assert r.json()["config"]["tools"] == ["read_file", "grep"]


def _serve_args(tmp_path) -> Namespace:
	return Namespace(
		host="127.0.0.1",
		port=0,
		data_dir=str(tmp_path),
		profile="local",
		background=False,
		uds=None,
		parent_watch=False,
		extension=[],
		no_extensions=False,
	)


def test_serve_refuses_token_and_tenants_together(tmp_path, monkeypatch):
	from flow import config

	cli_main = importlib.import_module("flow.cli.main")
	monkeypatch.setattr(config, "AUTH_TOKEN", "secret")
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	monkeypatch.setattr(config, "TENANTS_FILE", str(tmp_path / "tenants.json"))
	with pytest.raises(DaemonError, match="not both"):
		cli_main._serve(_serve_args(tmp_path))


def test_serve_wraps_tenants_file_errors(tmp_path, monkeypatch):
	from flow import config

	cli_main = importlib.import_module("flow.cli.main")
	monkeypatch.setattr(config, "AUTH_TOKEN", None)
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	monkeypatch.setattr(config, "TENANTS_FILE", str(tmp_path / "missing.json"))
	with pytest.raises(DaemonError, match="cannot load FLOW_TENANTS_FILE"):
		cli_main._serve(_serve_args(tmp_path))
