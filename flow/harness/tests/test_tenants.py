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
				"site1.localhost": {
					"token": "abc",
					"allowed_roots": ["/srv/site1"],
					"callback_hosts": ["site1.localhost:8000"],
				},
				"site2.localhost": {"token": "def", "allowed_roots": ["/srv/site2"]},
			}
		)
	)
	tenants = load_tenants(str(path))
	assert tenants == [
		Tenant(
			site="site1.localhost",
			token="abc",
			allowed_roots=("/srv/site1",),
			callback_hosts=("site1.localhost:8000",),
		),
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
			'{"site1": {"token": "a", "allowed_roots": ["/x"], "callback_hosts": "site1:8000"}}',
			"callback_hosts must be a list",
		),
		(
			'{"site1": {"token": "a", "allowed_roots": ["/x"], "callback_hosts": ["site1:8000", ""]}}',
			"callback_hosts must be a list",
		),
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


def test_for_site_partitions_sessions_and_credentials(tmp_path):
	store = _store(tmp_path)
	site = store.for_site("site1.localhost")
	assert site.sessions_dir == str(tmp_path / "data" / "tenants" / "site1.localhost" / "sessions")
	# own credential store: a bench-wide key is never a site's to consume
	assert site.credential_store.path == str(
		tmp_path / "data" / "tenants" / "site1.localhost" / "credentials.json"
	)
	store.credential_store.set_api_key("anthropic", "sk-shared")
	assert site.credential_store.get("anthropic") is None
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


def test_tenant_tokens_never_reach_provider_routes(tmp_path):
	"""The credential store is daemon-wide; a site token managing it could tamper
	with every other site's providers — so tenants mode disables those routes."""
	c = TestClient(create_app(_store(tmp_path), tenants=TENANTS))
	auth = _auth("token-one")
	assert c.get("/providers", headers=auth).status_code == 403
	r = c.post("/providers/anthropic/api-key", json={"api_key": "sk-x"}, headers=auth)
	assert r.status_code == 403
	assert "server policy" in r.json()["detail"]


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


def test_per_site_callback_hosts(tmp_path):
	tenants = [
		Tenant(site="site1.localhost", token="token-one", callback_hosts=("site1.localhost:8000",)),
		Tenant(site="site2.localhost", token="token-two"),
	]
	c = TestClient(create_app(_store(tmp_path, callback_hosts=["shared.localhost:8000"]), tenants=tenants))

	def create(token: str, host: str) -> int:
		body = {"cwd": str(tmp_path), "callback_url": f"http://{host}/api/method/tool_callback"}
		return c.post("/sessions", json=body, headers=_auth(token)).status_code

	# a site's own list replaces the daemon-wide fence
	assert create("token-one", "site1.localhost:8000") == 200
	assert create("token-one", "shared.localhost:8000") == 400
	# no list of its own: site2 keeps the daemon-wide fence
	assert create("token-two", "shared.localhost:8000") == 200
	assert create("token-two", "site1.localhost:8000") == 400


def test_site_callback_hosts_satisfy_deployed(tmp_path):
	"""Deployed refuses callbacks until hosts are configured; a site's own list is
	enough, so a bench needs neither FLOW_CALLBACK_HOSTS nor a restart per site."""
	store = _store(tmp_path, tool_allowlist=DEPLOYED.tool_allowlist, callback_hosts=DEPLOYED.callback_hosts)
	tenants = [
		Tenant(site="site1.localhost", token="token-one", callback_hosts=("site1.localhost:8000",)),
		Tenant(site="site2.localhost", token="token-two"),
	]
	c = TestClient(create_app(store, policy=DEPLOYED, tenants=tenants))

	def create(token: str, host: str) -> int:
		body = {"cwd": str(tmp_path), "callback_url": f"http://{host}/api/method/tool_callback"}
		return c.post("/sessions", json=body, headers=_auth(token)).status_code

	assert create("token-one", "site1.localhost:8000") == 200
	assert create("token-two", "site2.localhost:8000") == 400


def test_tenants_satisfy_deployed_auth(tmp_path):
	store = _store(tmp_path, tool_allowlist=DEPLOYED.tool_allowlist, callback_hosts=DEPLOYED.callback_hosts)
	c = TestClient(create_app(store, policy=DEPLOYED, tenants=TENANTS))
	r = c.post("/sessions", json={"cwd": str(tmp_path)}, headers=_auth("token-one"))
	assert r.status_code == 200
	assert r.json()["config"]["tools"] == ["read", "grep"]


def _entry(root, token="token-one") -> dict:
	return {"token": token, "allowed_roots": [str(root)]}


def _live_client(tmp_path, sites: dict) -> tuple[TestClient, object]:
	path = tmp_path / "tenants.json"
	path.write_text(json.dumps(sites))
	client = TestClient(create_app(_store(tmp_path), tenants=load_tenants(str(path)), tenants_file=str(path)))
	return client, path


def test_new_site_in_tenants_file_works_without_restart(tmp_path):
	c, path = _live_client(tmp_path, {"site1.localhost": _entry(tmp_path)})
	assert c.get("/sessions", headers=_auth("token-two")).status_code == 401
	path.write_text(
		json.dumps({"site1.localhost": _entry(tmp_path), "site2.localhost": _entry(tmp_path, "token-two")})
	)
	r = c.post("/sessions", json={"cwd": str(tmp_path)}, headers=_auth("token-two"))
	assert r.status_code == 200
	assert c.get("/sessions", headers=_auth("token-one")).status_code == 200


def test_reload_route_requires_a_site_token(tmp_path):
	c, _path = _live_client(tmp_path, {"site1.localhost": _entry(tmp_path)})
	assert c.post("/tenants/reload").status_code == 401
	assert c.post("/tenants/reload", headers=_auth("nope")).status_code == 401
	assert c.post("/tenants/reload", headers=_auth("token-one")).json() == {"sites": 1}


def test_reload_without_a_tenants_file_changes_nothing(tmp_path):
	c = TestClient(create_app(_store(tmp_path), tenants=TENANTS))
	assert c.post("/tenants/reload", headers=_auth("token-one")).json() == {"sites": 2}


def test_site_removed_from_tenants_file_is_refused(tmp_path):
	sites = {"site1.localhost": _entry(tmp_path), "site2.localhost": _entry(tmp_path, "token-two")}
	c, path = _live_client(tmp_path, sites)
	assert c.get("/sessions", headers=_auth("token-two")).status_code == 200
	path.write_text(json.dumps({"site1.localhost": _entry(tmp_path)}))
	assert c.post("/tenants/reload", headers=_auth("token-one")).json() == {"sites": 1}
	assert c.get("/sessions", headers=_auth("token-two")).status_code == 401
	assert c.get("/sessions", headers=_auth("token-one")).status_code == 200


def test_broken_tenants_reload_answers_400_and_keeps_the_last_good_list(tmp_path):
	c, path = _live_client(tmp_path, {"site1.localhost": _entry(tmp_path)})
	for content in ("not json", "{}"):  # unreadable, and emptied of every site
		path.write_text(content)
		assert c.post("/tenants/reload", headers=_auth("token-one")).status_code == 400
	assert c.get("/sessions", headers=_auth("token-one")).status_code == 200


def test_tenants_reload_applies_changed_roots(tmp_path):
	old, new = tmp_path / "old", tmp_path / "new"
	old.mkdir()
	new.mkdir()
	c, path = _live_client(tmp_path, {"site1.localhost": _entry(old)})

	def create(root) -> int:
		return c.post("/sessions", json={"cwd": str(root)}, headers=_auth("token-one")).status_code

	started = c.post("/sessions", json={"cwd": str(old)}, headers=_auth("token-one"))
	assert started.status_code == 200
	path.write_text(json.dumps({"site1.localhost": _entry(new)}))
	assert c.post("/tenants/reload", headers=_auth("token-one")).status_code == 200
	assert create(new) == 200
	assert create(old) == 400
	sid = started.json()["session_id"]  # the session already loaded is fenced out too
	assert c.get(f"/sessions/{sid}", headers=_auth("token-one")).status_code == 400


def test_tenants_reload_applies_changed_callback_hosts(tmp_path):
	def entry(host: str) -> dict:
		return {"token": "token-one", "allowed_roots": [str(tmp_path)], "callback_hosts": [host]}

	c, path = _live_client(tmp_path, {"site1.localhost": entry("a.localhost:8000")})

	def create(host: str) -> int:
		body = {"cwd": str(tmp_path), "callback_url": f"http://{host}/cb"}
		return c.post("/sessions", json=body, headers=_auth("token-one")).status_code

	assert create("a.localhost:8000") == 200
	path.write_text(json.dumps({"site1.localhost": entry("b.localhost:8000")}))
	assert c.post("/tenants/reload", headers=_auth("token-one")).status_code == 200
	assert create("b.localhost:8000") == 200
	assert create("a.localhost:8000") == 400


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
