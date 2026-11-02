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


def test_load_tenants_parses_the_template_and_rejects_broken_ones():
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
	folder, _ = _two_sites(tmp_path)
	(tmp_path / "sites" / "assets").mkdir()
	tenants = _tenants(
		tmp_path,
		allowed_roots=(str(tmp_path / "sites" / "{site}"), "/srv/apps"),
		callback_hosts=("127.0.0.1:8000",),
		callback_headers={"X-Frappe-Site-Name": "{site}"},
		ignore_hidden_files=True,
		data_dir=str(tmp_path / "sites" / "{site}" / "flow"),
		extensions=(str(tmp_path / "sites" / "{site}" / "flow" / "extensions"),),
	)
	assert tenants.sites() == ["site1.localhost", "site2.localhost"]  # every name with a token file
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


def test_a_sites_token_file_is_read_on_every_request(tmp_path, monkeypatch):
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
	data_dir = str(tmp_path / "sites" / "{site}" / "flow")
	with TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path, data_dir=data_dir))) as c:
		assert c.get("/healthz").status_code == 200  # serves with no site at all
		assert c.get("/sessions", headers=ONE).status_code == 401
		cwd = _site(tmp_path, "site1.localhost", "token-one")  # moved onto this bench by a deploy
		assert c.post("/sessions", json={"cwd": cwd}, headers=ONE).status_code == 200
		_site(tmp_path, "site1.localhost", "token-new")
		assert c.get("/sessions", headers=ONE).status_code == 401
		new = _auth("site1.localhost", "token-new")
		assert c.get("/sessions", headers=new).status_code == 200
		partition = os.path.join(cwd, "flow")
		assert events == [str(tmp_path / "data"), partition]
		assert made == ["site1.localhost"]  # a new secret keeps the partition and its live sessions

		# Flow uninstalled: its secret and data removed; other sites carry on
		_site(tmp_path, "site2.localhost", "token-two")
		_site(tmp_path, "site1.localhost", "")
		assert c.get("/sessions", headers=new).status_code == 401
		assert c.get("/sessions", headers=TWO).status_code == 200
		shutil.rmtree(partition)

		# a reinstall makes a new secret and works without a restart
		_site(tmp_path, "site1.localhost", "token-again")
		again = _auth("site1.localhost", "token-again")
		assert c.get("/sessions", headers=again).json()["sessions"] == []
		assert c.post("/sessions", json={"cwd": cwd}, headers=again).status_code == 200
	assert made == ["site1.localhost", "site2.localhost", "site1.localhost"]


def test_a_site_token_reaches_only_its_own_sessions(tmp_path):
	one, two = _two_sites(tmp_path)
	c = TestClient(create_app(_store(tmp_path), tenants=_tenants(tmp_path)))
	r = c.post("/sessions", json={"cwd": one}, headers=ONE)
	assert r.status_code == 200
	sid = r.json()["session_id"]
	assert c.get(f"/sessions/{sid}", headers=ONE).status_code == 200
	assert c.get("/sessions", headers=TWO).json()["sessions"] == []
	assert c.get(f"/sessions/{sid}", headers=TWO).status_code == 404
	assert c.get(f"/sessions/{sid}/entries", headers=TWO).status_code == 404
	assert c.delete(f"/sessions/{sid}", headers=TWO).status_code == 404
	# no site, a wrong token, or another site's token
	for headers in (
		None,
		{"Authorization": "Bearer token-one"},
		_auth("site1.localhost", "wrong"),
		_auth("site2.localhost", "token-one"),
	):
		assert c.get("/sessions", headers=headers).status_code == 401, headers
	assert c.get("/healthz").status_code == 200

	# nor another site's folder
	r = c.post("/sessions", json={"cwd": two}, headers=ONE)
	assert r.status_code == 400
	assert "allowed root" in r.json()["detail"]

	# the credential store, the settings file and the home folder are daemon-wide, so no site token may manage them
	assert c.get("/providers", headers=ONE).status_code == 403
	r = c.post("/providers/anthropic/api-key", json={"api_key": "sk-x"}, headers=ONE)
	assert r.status_code == 403
	assert "server policy" in r.json()["detail"]
	assert c.patch("/settings", json={"settings": {"theme": "dark"}}, headers=ONE).status_code == 403
	assert c.get("/workspaces", headers=ONE).status_code == 403


def test_sink_events_include_the_site(tmp_path):
	for name, policy in (("local", None), ("deployed", DEPLOYED)):
		root = tmp_path / name
		received = []
		store = _store(root, event_sink=lambda sid, event: received.append((sid, event)))
		sites = _two_sites(root)
		c = TestClient(create_app(store, tenants=_tenants(root), policy=policy))
		for cwd, auth in zip(sites, (ONE, TWO), strict=True):
			# the same session id on two sites
			body = {"model": "mock", "cwd": cwd, "session_id": "shared-id"}
			assert c.post("/sessions", json=body, headers=auth).status_code == 200, name
			response = c.post(
				"/sessions/shared-id/run",
				params={"wait": "true"},
				json={"message": "hello"},
				headers=auth,
			)
			assert response.status_code == 200, name

		assert {event["site"] for _sid, event in received} == {"site1.localhost", "site2.localhost"}, name
		assert {sid for sid, _event in received} == {"shared-id"}, name


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
	store = _store(tmp_path / "local", callback_hosts=["shared.localhost:8000"])
	c = TestClient(create_app(store, tenants=_tenants(tmp_path, callback_hosts=("bench.localhost:8000",))))
	assert _callback_status(c, one, ONE, "bench.localhost:8000") == 200
	assert _callback_status(c, one, ONE, "shared.localhost:8000") == 400

	# deployed refuses callbacks until hosts are configured; the template's list is
	# enough, so a bench needs no FLOW_CALLBACK_HOSTS
	store = _store(
		tmp_path / "deployed", tool_allowlist=DEPLOYED.tool_allowlist, callback_hosts=DEPLOYED.callback_hosts
	)
	tenants = _tenants(tmp_path, callback_hosts=("127.0.0.1:8000",))
	c = TestClient(create_app(store, policy=DEPLOYED, tenants=tenants))
	assert _callback_status(c, one, ONE, "127.0.0.1:8000") == 200
	assert _callback_status(c, one, ONE, "evil.example.com") == 400
	# tenants satisfy deployed auth, and its allowlist caps a site's tools
	r = c.post("/sessions", json={"cwd": one}, headers=ONE)
	assert r.status_code == 200
	assert r.json()["config"]["tools"] == ["read"]


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


def test_serve_refuses_a_bad_tenants_config(tmp_path, monkeypatch):
	from flow_harness import config

	cli_main = importlib.import_module("flow_harness.cli.main")
	monkeypatch.setattr(config, "AUTH_TOKEN_FILE", None)
	for token, tenants, match in (
		("secret", '{"token_file": "/s/{site}/t.json", "allowed_roots": ["/s"]}', "not both"),
		(
			None,
			'{"token_file": "/s/t.json", "allowed_roots": ["/s"]}',
			"cannot load FLOW_TENANTS: token_file must",
		),
	):
		monkeypatch.setattr(config, "AUTH_TOKEN", token)
		monkeypatch.setattr(config, "TENANTS", tenants)
		with pytest.raises(DaemonError, match=match):
			cli_main._serve(_serve_args(tmp_path))
