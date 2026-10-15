"""Multi-tenant mode: the template, per-site lookup and auth, and per-site isolation."""

import importlib
import json
import os
import shutil
from argparse import Namespace
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from flow_harness.cli.daemon import DaemonError
from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.policy import DEPLOYED
from flow_harness.server.tenants import Tenant, TenantTemplate, load_tenants
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore


def _store(tmp_path, **store_kw) -> SessionStore:
	store_kw.setdefault("credential_store", CredentialStore(str(tmp_path / "credentials.json")))
	return SessionStore(str(tmp_path / "data"), **store_kw)


def _tenants(tmp_path, **template) -> TenantTemplate:
	"""Each site is a folder under tmp_path/sites holding its token in site.json."""
	template.setdefault("allowed_roots", (str(tmp_path / "sites" / "{site}"),))
	return TenantTemplate(
		token_file=str(tmp_path / "sites" / "{site}" / "site.json"), token_key="token", **template
	)


def _site(tmp_path, name: str, token: str, **settings) -> str:
	folder = tmp_path / "sites" / name
	folder.mkdir(parents=True, exist_ok=True)
	(folder / "site.json").write_text(json.dumps({"token": token, **settings}))
	return str(folder)


def _auth(site: str, token: str) -> dict[str, str]:
	return {"Authorization": f"Bearer {token}", "X-Flow-Site": site}


def _two_sites(tmp_path) -> tuple[str, str]:
	return _site(tmp_path, "site1.localhost", "token-one"), _site(tmp_path, "site2.localhost", "token-two")


ONE = _auth("site1.localhost", "token-one")
TWO = _auth("site2.localhost", "token-two")


def test_load_tenants_parses_the_template():
	template = {
		"token_file": "/srv/{site}/site_config.json",
		"token_key": "flow_server_secret",
		"allowed_roots": ["/srv/{site}/public/files", "/srv/apps"],
		"ignore_hidden_files": True,
		"callback_hosts": ["127.0.0.1:8000"],
		"callback_headers": {"X-Frappe-Site-Name": "{site}"},
		"data_dir": "/srv/{site}/private/flow",
		"extensions": ["/srv/{site}/private/flow/extensions"],
	}
	assert load_tenants(json.dumps(template)) == TenantTemplate(
		token_file="/srv/{site}/site_config.json",
		token_key="flow_server_secret",
		allowed_roots=("/srv/{site}/public/files", "/srv/apps"),
		ignore_hidden_files=True,
		callback_hosts=("127.0.0.1:8000",),
		callback_headers={"X-Frappe-Site-Name": "{site}"},
		data_dir="/srv/{site}/private/flow",
		extensions=("/srv/{site}/private/flow/extensions",),
	)
	minimal = load_tenants(
		'{"token_file": "/srv/{site}/t.json", "token_key": "k", "allowed_roots": ["/srv/{site}"]}'
	)
	assert (minimal.callback_hosts, minimal.data_dir) == (None, None)


def test_load_tenants_rejects_broken_templates():
	token_fields = '"token_file": "/s/{site}/t.json", "token_key": "k"'
	base = f'{token_fields}, "allowed_roots": ["/x"]'
	cases = [
		("not json", "Expecting value"),
		("[]", "must be a JSON object"),
		('{"allowed_roots": ["/x"]}', "token_file must be an absolute path containing {site}"),
		('{"token_file": "s/{site}/t.json", "allowed_roots": ["/x"]}', "token_file must be an absolute"),
		('{"token_file": "/s/t.json", "allowed_roots": ["/x"]}', "token_file must be an absolute"),
		(f'{{{base}, "alowed_roots": ["/x"]}}', "unknown keys: alowed_roots"),
		('{"token_file": "/s/{site}/t.json", "allowed_roots": ["/x"]}', "token_key must be"),
		('{"token_file": "/s/{site}/t.json", "token_key": "", "allowed_roots": ["/x"]}', "token_key must be"),
		(f"{{{token_fields}}}", "allowed_roots is required"),
		(f'{{{token_fields}, "allowed_roots": []}}', "allowed_roots is required"),
		(f'{{{token_fields}, "allowed_roots": ["/x", 3]}}', "allowed_roots is required"),
		(f'{{{base}, "ignore_hidden_files": 1}}', "must be a boolean"),
		(f'{{{base}, "callback_hosts": "a:8000"}}', "callback_hosts must be a list"),
		(f'{{{base}, "callback_hosts": ["a:8000", ""]}}', "callback_hosts must be a list"),
		(f'{{{base}, "callback_headers": {{"X-Site": 1}}}}', "callback_headers must map"),
		(f'{{{base}, "data_dir": "flow/{{site}}"}}', "data_dir must be an absolute path"),
		(f'{{{base}, "data_dir": "/srv/flow"}}', "every site would share one"),
		(f'{{{base}, "extensions": "/x/ext"}}', "extensions must be a list of absolute paths"),
		(f'{{{base}, "extensions": ["ext"]}}', "extensions must be a list of absolute paths"),
	]
	for content, match in cases:
		with pytest.raises(ValueError, match=match):
			load_tenants(content)


def test_lookup_fills_the_template_from_the_sites_own_file(tmp_path):
	folder = _site(tmp_path, "site1.localhost", "token-one")
	tenants = _tenants(
		tmp_path,
		allowed_roots=(str(tmp_path / "sites" / "{site}"), "/srv/apps"),
		callback_hosts=("127.0.0.1:8000",),
		callback_headers={"X-Frappe-Site-Name": "{site}"},
		ignore_hidden_files=True,
		data_dir=str(tmp_path / "sites" / "{site}" / "flow"),
		extensions=(str(tmp_path / "sites" / "{site}" / "flow" / "extensions"),),
	)
	assert tenants.lookup("site1.localhost") == Tenant(
		site="site1.localhost",
		token="token-one",
		allowed_roots=(folder, "/srv/apps"),
		callback_hosts=("127.0.0.1:8000",),
		callback_headers={"X-Frappe-Site-Name": "site1.localhost"},
		ignore_hidden_files=True,
		data_dir=os.path.join(folder, "flow"),
		extensions=(os.path.join(folder, "flow", "extensions"),),
	)
	_site(tmp_path, "tokenless.localhost", "")
	_site(tmp_path, "broken.localhost", "")
	(tmp_path / "sites" / "broken.localhost" / "site.json").write_text('{"tok')
	for name in ("missing.localhost", "tokenless.localhost", "broken.localhost", "..", ".hidden", "a/b", ""):
		assert tenants.lookup(name) is None, name


def test_sites_lists_every_name_with_a_token_file(tmp_path):
	_two_sites(tmp_path)
	(tmp_path / "sites" / "assets").mkdir()
	assert _tenants(tmp_path).sites() == ["site1.localhost", "site2.localhost"]


def test_path_for_site_moves_another_sites_folder_to_this_one():
	tenants = TenantTemplate(
		token_file="/b/sites/{site}/t.json", token_key="t", allowed_roots=("/b/sites/{site}/files", "/b/apps")
	)
	assert tenants.path_for_site("new", "/b/sites/old/files") == "/b/sites/new/files"
	for path in ("/b/sites/new/files", "/b/sites/old/files_x", "/b/apps", "/b/appsx", "/elsewhere"):
		assert tenants.path_for_site("new", path) == path


def test_for_site_partitions_sessions_and_credentials(tmp_path):
	store = _store(tmp_path)
	site = store.for_site("site1.localhost", ignore_hidden_files=True)
	assert site.closing is store.closing  # site streams end with the daemon
	assert site.sessions_dir == str(tmp_path / "data" / "tenants" / "site1.localhost" / "sessions")
	# own credential store: a bench-wide key is never a site's to consume
	assert site.credential_store.path == str(
		tmp_path / "data" / "tenants" / "site1.localhost" / "credentials.json"
	)
	assert site.ignore_hidden_files is True
	assert site.create(SessionConfig(cwd=str(tmp_path))).ignore_hidden_files is True
	store.credential_store.set_api_key("anthropic", "sk-shared")
	assert site.credential_store.get("anthropic") is None
	other = store.for_site("site2.localhost")
	assert other.sessions_dir != site.sessions_dir
	own = store.for_site("site3.localhost", data_dir=str(tmp_path / "site3" / "flow"))
	assert own.sessions_dir == str(tmp_path / "site3" / "flow" / "sessions")
	assert own.credential_store.path == str(tmp_path / "site3" / "flow" / "credentials.json")


def test_for_site_rejects_unsafe_names(tmp_path):
	store = _store(tmp_path)
	for name in ("..", ".", "a/b", "../escape", ".hidden", ""):
		with pytest.raises(ValueError, match="invalid site name"):
			store.for_site(name)


def test_startup_reports_unconfirmed_run_ends_in_every_partition(tmp_path, monkeypatch):
	events = []
	monkeypatch.setattr(
		SessionStore, "report_unconfirmed_run_ends", lambda store: events.append(store.data_dir)
	)

	@asynccontextmanager
	async def sink_lifespan(app):  # the Redis sink's, in a daemon that has one
		events.append("sink up")
		yield
		events.append("sink down")

	_two_sites(tmp_path)
	store = _store(tmp_path)
	with TestClient(create_app(store, tenants=_tenants(tmp_path), lifespan=sink_lifespan)):
		pass
	assert events == [
		"sink up",
		store.data_dir,
		str(tmp_path / "data" / "tenants" / "site1.localhost"),
		str(tmp_path / "data" / "tenants" / "site2.localhost"),
		"sink down",
	]


def test_a_site_arriving_later_reports_its_run_ends_on_its_first_request(tmp_path, monkeypatch):
	events = []
	monkeypatch.setattr(
		SessionStore, "report_unconfirmed_run_ends", lambda store: events.append(store.data_dir)
	)
	made = []
	for_site = SessionStore.for_site
	monkeypatch.setattr(
		SessionStore,
		"for_site",
		lambda store, site, *a, **kw: made.append(site) or for_site(store, site, *a, **kw),
	)
	with TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path))) as c:
		assert c.get("/healthz").status_code == 200  # serves with no site at all
		assert c.get("/sessions", headers=ONE).status_code == 401
		_site(tmp_path, "site1.localhost", "token-one")  # moved onto this bench by a deploy
		assert c.get("/sessions", headers=ONE).status_code == 200
		_site(tmp_path, "site1.localhost", "token-new")
		assert c.get("/sessions", headers=ONE).status_code == 401
		assert c.get("/sessions", headers=_auth("site1.localhost", "token-new")).status_code == 200
	partition = str(tmp_path / "data" / "tenants" / "site1.localhost")
	assert events == [str(tmp_path / "data"), partition]
	assert made == ["site1.localhost"]  # a new secret keeps the partition and its live sessions


def test_sites_only_see_their_own_sessions(tmp_path):
	cwd, _ = _two_sites(tmp_path)
	c = TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path)))
	r = c.post("/sessions", json={"cwd": cwd}, headers=ONE)
	assert r.status_code == 200
	sid = r.json()["session_id"]
	assert c.get(f"/sessions/{sid}", headers=ONE).status_code == 200
	sessions = c.get("/sessions", headers=TWO).json()["sessions"]
	assert sessions == []
	assert c.get(f"/sessions/{sid}", headers=TWO).status_code == 404
	assert c.get(f"/sessions/{sid}/entries", headers=TWO).status_code == 404
	assert c.delete(f"/sessions/{sid}", headers=TWO).status_code == 404
	assert c.get("/sessions").status_code == 401
	assert c.get("/sessions", headers={"Authorization": "Bearer token-one"}).status_code == 401
	assert c.get("/sessions", headers=_auth("site1.localhost", "wrong")).status_code == 401
	# a token opens only its own site
	assert c.get("/sessions", headers=_auth("site2.localhost", "token-one")).status_code == 401
	assert c.get("/healthz").status_code == 200


def test_tenant_tokens_never_reach_provider_routes(tmp_path):
	"""The credential store is daemon-wide; a site token managing it could tamper
	with every other site's providers — so tenants mode disables those routes."""
	_two_sites(tmp_path)
	c = TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path)))
	assert c.get("/providers", headers=ONE).status_code == 403
	r = c.post("/providers/anthropic/api-key", json={"api_key": "sk-x"}, headers=ONE)
	assert r.status_code == 403
	assert "server policy" in r.json()["detail"]


def test_same_session_id_allowed_on_two_sites(tmp_path):
	sites = _two_sites(tmp_path)
	c = TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path)))
	for cwd, auth in zip(sites, (ONE, TWO), strict=True):
		body = {"cwd": cwd, "session_id": "shared-id"}
		assert c.post("/sessions", json=body, headers=auth).status_code == 200


@pytest.mark.parametrize("policy", [None, DEPLOYED], ids=["local", "deployed"])
def test_sink_events_include_the_site(tmp_path, policy):
	received = []
	store = _store(tmp_path, event_sink=lambda sid, event: received.append((sid, event)))
	sites = _two_sites(tmp_path)
	c = TestClient(create_app(store, tenants=_tenants(tmp_path), policy=policy))
	for cwd, auth in zip(sites, (ONE, TWO), strict=True):
		sid = c.post(
			"/sessions",
			json={"model": "mock", "cwd": cwd, "session_id": "shared-id"},
			headers=auth,
		).json()["session_id"]
		response = c.post(
			f"/sessions/{sid}/run",
			params={"wait": "true"},
			json={"message": "hello"},
			headers=auth,
		)
		assert response.status_code == 200

	assert {event["site"] for _sid, event in received} == {"site1.localhost", "site2.localhost"}
	assert {sid for sid, _event in received} == {"shared-id"}


def test_each_site_is_fenced_to_its_own_folder(tmp_path):
	one, two = _two_sites(tmp_path)
	c = TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path)))
	assert c.post("/sessions", json={"cwd": one}, headers=ONE).status_code == 200
	r = c.post("/sessions", json={"cwd": two}, headers=ONE)
	assert r.status_code == 400
	assert "allowed root" in r.json()["detail"]


HELLO_EXTENSION = """
from flow_harness.tools import ToolResult, tool

@tool
async def hello(who: str = "world", *, ctx) -> ToolResult:
    \"\"\"Greet someone by name.\"\"\"
    return ToolResult(content=f"Hello, {who}!")

def setup(flow):
    flow.register_tool(hello)
"""


def _extension_tools(client: TestClient, auth: dict[str, str]) -> list[str]:
	rows = client.get("/tools", headers=auth).json()["tools"]
	return [row["name"] for row in rows if row["extension"]]


def test_per_site_extensions_stay_with_their_site(tmp_path):
	one, _ = _two_sites(tmp_path)
	folder = os.path.join(one, "extensions")
	os.mkdir(folder)
	with open(os.path.join(folder, "hello.py"), "w") as file:
		file.write(HELLO_EXTENSION)
	store = _store(tmp_path)
	extensions = (str(tmp_path / "sites" / "{site}" / "extensions"),)
	c = TestClient(create_app(store, tenants=_tenants(tmp_path, extensions=extensions)))
	assert _extension_tools(c, ONE) == ["hello"]
	assert _extension_tools(c, TWO) == []
	# a folder that does not exist yet is skipped without a diagnostic
	missing = str(tmp_path / "sites" / "site2.localhost" / "extensions")
	assert store.for_site("site2.localhost", extensions=(missing,)).extension_runtime.diagnostics == ()


def _callback_status(c: TestClient, cwd: str, auth: dict[str, str], host: str) -> int:
	body = {"cwd": cwd, "callback_url": f"http://{host}/api/method/tool_callback"}
	return c.post("/sessions", json=body, headers=auth).status_code


def test_site_callback_hosts_replace_the_daemon_wide_fence(tmp_path):
	one, _ = _two_sites(tmp_path)
	store = _store(tmp_path, callback_hosts=["shared.localhost:8000"])
	c = TestClient(create_app(store, tenants=_tenants(tmp_path, callback_hosts=("bench.localhost:8000",))))
	assert _callback_status(c, one, ONE, "bench.localhost:8000") == 200
	assert _callback_status(c, one, ONE, "shared.localhost:8000") == 400


def test_site_callback_hosts_satisfy_deployed(tmp_path):
	"""Deployed refuses callbacks until hosts are configured; the template's list is
	enough, so a bench needs no FLOW_CALLBACK_HOSTS."""
	one, _ = _two_sites(tmp_path)
	store = _store(tmp_path, tool_allowlist=DEPLOYED.tool_allowlist, callback_hosts=DEPLOYED.callback_hosts)
	tenants = _tenants(tmp_path, callback_hosts=("127.0.0.1:8000",))
	c = TestClient(create_app(store, policy=DEPLOYED, tenants=tenants))
	assert _callback_status(c, one, ONE, "127.0.0.1:8000") == 200
	assert _callback_status(c, one, ONE, "evil.example.com") == 400


def test_tenants_satisfy_deployed_auth(tmp_path):
	one, _ = _two_sites(tmp_path)
	store = _store(tmp_path, tool_allowlist=DEPLOYED.tool_allowlist, callback_hosts=DEPLOYED.callback_hosts)
	c = TestClient(create_app(store, policy=DEPLOYED, tenants=_tenants(tmp_path)))
	r = c.post("/sessions", json={"cwd": one}, headers=ONE)
	assert r.status_code == 200
	assert r.json()["config"]["tools"] == ["read"]


def test_a_site_whose_token_is_gone_is_refused(tmp_path):
	_two_sites(tmp_path)
	c = TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path)))
	assert c.get("/sessions", headers=TWO).status_code == 200
	_site(tmp_path, "site2.localhost", "")  # Flow uninstalled: its secret removed
	assert c.get("/sessions", headers=TWO).status_code == 401
	assert c.get("/sessions", headers=ONE).status_code == 200


def test_a_reinstalled_site_works_without_a_restart(tmp_path):
	cwd = _site(tmp_path, "site1.localhost", "token-one")
	data_dir = str(tmp_path / "sites" / "{site}" / "flow")
	c = TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path, data_dir=data_dir)))
	assert c.post("/sessions", json={"cwd": cwd}, headers=ONE).status_code == 200
	shutil.rmtree(os.path.join(cwd, "flow"))  # uninstall deletes the site's data
	_site(tmp_path, "site1.localhost", "token-new")  # reinstall makes a new secret
	again = _auth("site1.localhost", "token-new")
	assert c.get("/sessions", headers=again).json()["sessions"] == []
	assert c.post("/sessions", json={"cwd": cwd}, headers=again).status_code == 200


def _renaming_bench(tmp_path) -> TenantTemplate:
	sites = tmp_path / "sites"
	return _tenants(
		tmp_path,
		allowed_roots=(str(sites / "{site}" / "files"),),
		callback_hosts=("127.0.0.1:8000",),
		callback_headers={"X-Frappe-Site-Name": "{site}"},
		data_dir=str(sites / "{site}" / "flow"),
	)


def test_a_renamed_site_keeps_its_sessions(tmp_path):
	old = _site(tmp_path, "old.localhost", "token-one")
	os.mkdir(os.path.join(old, "files"))
	c = TestClient(create_app(_store(tmp_path), tenants=_renaming_bench(tmp_path)))
	cwd = os.path.join(old, "files")
	body = {"cwd": cwd, "callback_url": "http://127.0.0.1:8000/cb", "callback_headers": {"X-Other": "kept"}}
	created = c.post("/sessions", json=body, headers=_auth("old.localhost", "token-one")).json()
	assert created["config"]["callback_headers"] == {"X-Other": "kept", "X-Frappe-Site-Name": "old.localhost"}

	os.rename(old, tmp_path / "sites" / "new.localhost")  # Press moves the folder
	daemon = TestClient(create_app(_store(tmp_path), tenants=_renaming_bench(tmp_path)))
	sid = created["session_id"]
	assert daemon.get(f"/sessions/{sid}", headers=_auth("old.localhost", "token-one")).status_code == 401
	moved = daemon.get(f"/sessions/{sid}", headers=_auth("new.localhost", "token-one"))
	assert moved.status_code == 200
	config = moved.json()["config"]
	assert config["cwd"] == str(tmp_path / "sites" / "new.localhost" / "files")
	assert config["callback_headers"] == {"X-Other": "kept", "X-Frappe-Site-Name": "new.localhost"}


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
	from flow_harness import config

	cli_main = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "AUTH_TOKEN", "secret")
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	monkeypatch.setattr(config, "TENANTS", '{"token_file": "/s/{site}/t.json", "allowed_roots": ["/s"]}')
	with pytest.raises(DaemonError, match="not both"):
		cli_main._serve(_serve_args(tmp_path))


def test_serve_wraps_template_errors(tmp_path, monkeypatch):
	from flow_harness import config

	cli_main = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "AUTH_TOKEN", None)
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	monkeypatch.setattr(config, "TENANTS", '{"token_file": "/s/t.json", "allowed_roots": ["/s"]}')
	with pytest.raises(DaemonError, match="cannot load FLOW_TENANTS: token_file must"):
		cli_main._serve(_serve_args(tmp_path))
