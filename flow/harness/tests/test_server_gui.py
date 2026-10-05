"""Endpoints added for the web UI: providers, fs/pick, session delete/title,
context info, and CORS."""

import asyncio

import httpx
from fastapi.testclient import TestClient

from flow_harness.events import AssistantMessage, Usage
from flow_harness.model import Model, ModelRequest
from flow_harness.model.auth import resolve_model_auth
from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.utils.fspick import PickerUnavailable
from flow_harness.session.store import SessionStore


def _client(tmp_path, **app_kw):
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	return TestClient(create_app(store, **app_kw)), store


# --- providers --------------------------------------------------------------


def test_provider_catalog_reflects_stored_api_key(tmp_path):
	c, _ = _client(tmp_path)
	rows = {row["id"]: row for row in c.get("/providers").json()["providers"]}
	assert "openai" in rows and "codex" in rows
	assert rows["openai"]["credential_type"] is None

	assert c.post("/providers/openai/api-key", json={"key": "sk-test"}).json() == {"status": "saved"}
	rows = {row["id"]: row for row in c.get("/providers").json()["providers"]}
	assert rows["openai"]["configured"] is True
	assert rows["openai"]["credential_type"] == "api_key"
	assert rows["openai"]["source"] == "Stored API key"

	assert c.delete("/providers/openai").json() == {"status": "removed"}
	assert c.delete("/providers/openai").status_code == 404


def test_custom_provider_roundtrip(tmp_path):
	c, store = _client(tmp_path)
	body = {
		"name": "Local Ollama",
		"base_url": "http://localhost:11434/v1/",
		"models": ["ollama/llama3.2", "ollama/llama3.2", " ollama/qwen2.5 "],
		"api_key": "  ",  # blank means "no key", which local runtimes want
	}
	row = c.post("/providers/custom", json=body).json()["provider"]
	assert row["id"] == "custom-local-ollama"
	assert row["custom"] is True and row["configured"] is True
	assert row["source"] == "http://localhost:11434/v1"  # trailing slash trimmed
	assert row["models"] == ["ollama/llama3.2", "ollama/qwen2.5"]  # deduped, stripped

	credential = store.credential_store.get_custom(row["id"])
	assert credential is not None and credential.api_key is None

	# it shows up in the catalog, and its models resolve to its base URL
	assert any(p["id"] == row["id"] for p in c.get("/providers").json()["providers"])
	auth = asyncio.run(resolve_model_auth("ollama/llama3.2", store.credential_store))
	assert auth.base_url == "http://localhost:11434/v1"
	assert auth.provider_id == row["id"]

	# a second endpoint with the same name gets its own id, not a silent overwrite
	again = c.post("/providers/custom", json={**body, "models": ["ollama/x"]}).json()["provider"]
	assert again["id"] == "custom-local-ollama-2"

	assert c.delete(f"/providers/{row['id']}").json() == {"status": "removed"}
	assert store.credential_store.get(row["id"]) is None


def test_custom_provider_update(tmp_path):
	c, store = _client(tmp_path)
	body = {
		"name": "Local Ollama",
		"base_url": "http://localhost:11434/v1",
		"models": ["ollama/llama3.2"],
		"api_key": "secret",
	}
	row = c.post("/providers/custom", json=body).json()["provider"]

	# edit with a blank key and the same base_url: the stored key is kept
	edited = c.put(
		f"/providers/custom/{row['id']}",
		json={
			"name": "Gateway",
			"base_url": "http://localhost:11434/v1/",
			"models": ["gw/m1", "gw/m1", " gw/m2 "],
		},
	).json()["provider"]
	assert edited["id"] == row["id"]  # the id survives a rename
	assert edited["name"] == "Gateway"
	assert edited["models"] == ["gw/m1", "gw/m2"]
	credential = store.credential_store.get_custom(row["id"])
	assert credential is not None and credential.api_key == "secret"

	# repointing base_url with a blank key drops the key instead of leaking it
	moved = c.put(
		f"/providers/custom/{row['id']}",
		json={"name": "Gateway", "base_url": "http://gw:9/v1/", "models": ["gw/m1"]},
	).json()["provider"]
	assert moved["source"] == "http://gw:9/v1"
	assert store.credential_store.get_custom(row["id"]).api_key is None

	# a provided key replaces the stored one
	c.put(f"/providers/custom/{row['id']}", json={**body, "api_key": "rotated"})
	assert store.credential_store.get_custom(row["id"]).api_key == "rotated"

	# create-time validation applies, and only custom credentials are editable
	assert c.put(f"/providers/custom/{row['id']}", json={**body, "models": ["bare"]}).status_code == 422
	assert c.put("/providers/custom/custom-nope", json=body).status_code == 404
	c.post("/providers/openai/api-key", json={"key": "sk-test"})
	assert c.put("/providers/custom/openai", json=body).status_code == 404


def test_custom_provider_rejects_bad_input(tmp_path):
	c, _ = _client(tmp_path)
	base = {"name": "X", "base_url": "http://host/v1", "models": ["ollama/m"]}
	assert c.post("/providers/custom", json={**base, "base_url": "ftp://host"}).status_code == 422
	assert c.post("/providers/custom", json={**base, "base_url": "not-a-url"}).status_code == 422
	# credentials in the URL would be stored in cleartext and leak via the catalog
	assert c.post("/providers/custom", json={**base, "base_url": "http://u:p@host/v1"}).status_code == 422
	# a bare id can't be routed back to this endpoint
	assert c.post("/providers/custom", json={**base, "models": ["llama3.2"]}).status_code == 422
	assert c.post("/providers/custom", json={**base, "models": ["  "]}).status_code == 422
	assert c.post("/providers/custom", json={**base, "models": []}).status_code == 422
	assert c.post("/providers/custom", json={**base, "name": " "}).status_code == 422


def test_provider_endpoints_reject_bad_targets(tmp_path):
	c, _ = _client(tmp_path)
	assert c.post("/providers/nope/api-key", json={"key": "x"}).status_code == 400
	# codex is OAuth-only
	assert c.post("/providers/codex/api-key", json={"key": "x"}).status_code == 400
	assert c.post("/providers/openai/oauth/start").status_code == 400
	assert c.post("/providers/openai/api-key", json={"key": ""}).status_code == 422


async def test_oauth_flow_rejects_state_mismatch(tmp_path):
	# a single long-lived loop, like the daemon's: the flow's callback listener
	# thread must be shut down by /complete on the same loop it started on
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	transport = httpx.ASGITransport(app=create_app(store))
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
		assert (await c.get("/providers/codex/oauth/status")).json()["status"] == "idle"

		started = (await c.post("/providers/codex/oauth/start")).json()
		assert started["authorize_url"].startswith("https://")
		assert started["status"] in {"pending", "waiting_manual"}

		done = (
			await c.post(
				"/providers/codex/oauth/complete",
				json={"callback_url": "http://localhost:1455/auth/callback?code=abc&state=wrong"},
			)
		).json()
		assert done["status"] == "error"
		assert "state mismatch" in done["error"]
		# completing without a start is a client error
		response = await c.post("/providers/openai/oauth/complete", json={"callback_url": "http://x?code=1"})
		assert response.status_code == 400


# --- fs/pick ----------------------------------------------------------------


def test_fs_pick_returns_path_and_maps_unavailable_to_501(tmp_path, monkeypatch):
	c, _ = _client(tmp_path)
	monkeypatch.setattr("flow_harness.server.routes.fs.pick_folder", lambda: "/projects/demo")
	assert c.post("/fs/pick").json() == {"path": "/projects/demo"}

	monkeypatch.setattr("flow_harness.server.routes.fs.pick_folder", lambda: None)  # user cancelled
	assert c.post("/fs/pick").json() == {"path": None}

	def unavailable():
		raise PickerUnavailable("headless")

	monkeypatch.setattr("flow_harness.server.routes.fs.pick_folder", unavailable)
	assert c.post("/fs/pick").status_code == 501
	# a side-effectful dialog must never open off a plain GET (<img src=…>)
	assert c.get("/fs/pick").status_code == 405


# --- session title / context / delete ---------------------------------------


def test_session_title_and_context_fields(tmp_path):
	c, _ = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]

	detail = c.get(f"/sessions/{sid}").json()
	assert detail["title"] is None
	assert detail["context_window"] is None  # mock has no known window

	first_line = "summarize the repo"
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": first_line + "\nmore"})
	detail = c.get(f"/sessions/{sid}").json()
	assert detail["title"] == first_line
	assert detail["context_tokens"] > 0  # mock reports usage

	listed = c.get("/sessions").json()["sessions"]
	assert listed[0]["title"] == first_line


def test_patch_config_toggles_auto_approve_and_persists(tmp_path):
	c, store = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	assert c.get(f"/sessions/{sid}").json()["config"]["auto_approve"] is False

	data = c.patch(f"/sessions/{sid}/config", json={"auto_approve": True}).json()
	assert data["config"]["auto_approve"] is True
	# the live object the loop's tool gate reads flipped too
	assert store.get(sid).config.auto_approve is True
	# and the meta file persists it: a cold store sees the new mode
	fresh = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	assert fresh.get(sid).config.auto_approve is True

	# an empty patch changes nothing; unknown fields and sessions are rejected
	assert c.patch(f"/sessions/{sid}/config", json={}).json()["config"]["auto_approve"] is True
	assert c.patch(f"/sessions/{sid}/config", json={"model": "x"}).status_code == 422
	assert c.patch(f"/sessions/{sid}/config", json={"system_prompt": "replace"}).status_code == 422
	assert c.patch("/sessions/nope/config", json={"auto_approve": True}).status_code == 404


def test_patch_config_replaces_client_tools_and_confirmation_together(tmp_path):
	c, store = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={
			"model": "mock",
			"cwd": str(tmp_path),
			"client_tools": [{"type": "function", "function": {"name": "old"}}],
			"confirm_tools": ["old"],
		},
	).json()["session_id"]
	tools = [{"type": "function", "function": {"name": "new"}}]

	data = c.patch(f"/sessions/{sid}/config", json={"client_tools": tools, "confirm_tools": ["new"]}).json()
	assert data["config"]["client_tools"] == tools
	assert data["config"]["confirm_tools"] == ["new"]
	assert store.get(sid).config.client_tools == tools

	fresh = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	assert fresh.get(sid).config.client_tools == tools
	assert fresh.get(sid).config.confirm_tools == ["new"]
	assert c.patch(f"/sessions/{sid}/config", json={"client_tools": tools}).status_code == 400


def test_patch_config_replaces_server_tools(tmp_path):
	c, store = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={"model": "mock", "cwd": str(tmp_path), "tools": ["read"]},
	).json()["session_id"]

	data = c.patch(
		f"/sessions/{sid}/config",
		json={"tools": ["grep"]},
	).json()["config"]
	assert data["tools"] == ["grep"]
	assert set(store.get(sid).server_tools) == {"grep"}

	fresh = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	assert fresh.get(sid).config.tools == ["grep"]
	assert set(fresh.get(sid).server_tools) == {"grep"}


def test_patch_config_persists_every_field_or_none(tmp_path, monkeypatch):
	c, store = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path), "title": "Before"}).json()[
		"session_id"
	]
	before = store.get(sid).config.model_dump()
	tools = [{"type": "function", "function": {"name": "new"}}]
	patch = {
		"tools": ["grep"],
		"client_tools": tools,
		"confirm_tools": ["new"],
		"auto_approve": True,
		"title": "After",
	}

	def fail(session):
		raise OSError("disk full")

	# one write for the whole patch: when it fails, nothing changed in memory either
	monkeypatch.setattr(store, "save_meta", fail)
	assert c.patch(f"/sessions/{sid}/config", json=patch).status_code == 500
	assert store.get(sid).config.model_dump() == before

	monkeypatch.undo()
	data = c.patch(f"/sessions/{sid}/config", json=patch).json()["config"]
	assert (
		data["tools"],
		data["client_tools"],
		data["confirm_tools"],
		data["auto_approve"],
		data["title"],
	) == (
		["grep"],
		tools,
		["new"],
		True,
		"After",
	)
	fresh = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	config = fresh.get(sid).config
	assert (
		config.tools,
		config.client_tools,
		config.confirm_tools,
		config.auto_approve,
		config.title,
	) == (
		["grep"],
		tools,
		["new"],
		True,
		"After",
	)

	# an invalid field is refused before anything is applied
	assert c.patch(f"/sessions/{sid}/config", json={"auto_approve": False, "title": " "}).status_code == 400
	assert store.get(sid).config.auto_approve is True


async def test_patch_config_applies_during_active_run(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	transport = httpx.ASGITransport(app=create_app(store))
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
		sid = (await c.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
		run = asyncio.create_task(
			c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "go"})
		)
		await model.started.wait()

		response = await c.patch(f"/sessions/{sid}/config", json={"auto_approve": True})
		assert response.status_code == 200
		# the loop shares this config object, so the next tool gate skips approval
		assert store.get(sid).config.auto_approve is True
		model.release.set()
		assert (await run).json()["reason"] == "done"


def test_delete_session_removes_files(tmp_path):
	c, store = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})

	assert c.delete(f"/sessions/{sid}").json() == {"status": "deleted"}
	assert c.get(f"/sessions/{sid}").status_code == 404
	assert c.get("/sessions").json()["sessions"] == []
	assert not store.exists(sid)
	assert c.delete(f"/sessions/{sid}").status_code == 404


class _BlockingModel(Model):
	name = "blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()

	async def run(self, request: ModelRequest):
		self.started.set()
		await self.release.wait()
		yield AssistantMessage(content="done")
		yield Usage()


async def test_delete_running_session_conflicts(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	transport = httpx.ASGITransport(app=create_app(store))
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
		sid = (await c.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
		run = asyncio.create_task(
			c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "go"})
		)
		await model.started.wait()

		assert (await c.delete(f"/sessions/{sid}")).status_code == 409
		model.release.set()
		assert (await run).json()["reason"] == "done"
		assert (await c.delete(f"/sessions/{sid}")).json() == {"status": "deleted"}


# --- web UI mount -------------------------------------------------------------


def test_webui_mount_serves_shell_but_protects_api(tmp_path):
	webui = tmp_path / "webui"
	webui.mkdir()
	(webui / "index.html").write_text("<title>Flow</title>")
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	c = TestClient(create_app(store, auth_token="secret", webui_dir=str(webui)))

	# the static shell loads without a bearer; API paths still demand it
	assert "<title>Flow</title>" in c.get("/").text
	assert c.get("/sessions").status_code == 401
	assert c.get("/providers").status_code == 401
	assert c.get("/fs/file", params={"cwd": str(tmp_path), "path": "x"}).status_code == 401
	assert c.get("/sessions", headers={"Authorization": "Bearer secret"}).status_code == 200

	# without a webui dir, "/" stays a 404 and nothing is exempt
	bare = TestClient(create_app(store, auth_token="secret"))
	assert bare.get("/").status_code in (401, 404)


def test_webui_auth_bypass_covers_only_static_paths(tmp_path):
	"""The bypass is derived from the registered routes, so API roots outside the
	old hardcoded prefix list (e.g. /skills, /extensions) still demand a bearer."""
	webui = tmp_path / "webui"
	webui.mkdir()
	(webui / "index.html").write_text("<title>Flow</title>")
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	c = TestClient(create_app(store, auth_token="secret", webui_dir=str(webui)))

	assert c.get("/skills").status_code == 401
	assert c.get("/extensions/reload").status_code == 401
	assert c.get("/healthz").status_code == 200
	assert "<title>Flow</title>" in c.get("/").text


def test_tokenless_guard_refuses_foreign_hosts_and_origins(tmp_path):
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	c = TestClient(create_app(store), base_url="http://127.0.0.1:8787")  # loopback bind

	assert c.get("/healthz").json() == {"ok": True}
	# DNS rebinding: a hostile page's Host header is not loopback
	assert c.get("/sessions", headers={"Host": "evil.example"}).status_code == 400
	# cross-site request: foreign Origin refused even with a loopback Host
	assert (
		c.post(
			"/sessions", json={"cwd": str(tmp_path)}, headers={"Origin": "https://evil.example"}
		).status_code
		== 403
	)
	# the same-origin web UI passes
	assert c.get("/sessions", headers={"Origin": "http://127.0.0.1:8787"}).status_code == 200


def test_docs_routes_disabled(tmp_path):
	c, _ = _client(tmp_path)
	assert c.get("/openapi.json").status_code == 404
	assert c.get("/docs").status_code == 404


def test_preflight_passes_auth_when_token_set(tmp_path):
	c, _ = _client(tmp_path, auth_token="tok", cors_origins=["http://localhost:5199"])
	response = c.options(
		"/sessions",
		headers={"Origin": "http://localhost:5199", "Access-Control-Request-Method": "POST"},
	)
	assert response.status_code == 200
	assert response.headers["access-control-allow-origin"] == "http://localhost:5199"


# --- CORS --------------------------------------------------------------------


def test_cors_headers_only_when_configured(tmp_path):
	c, _ = _client(tmp_path, cors_origins=["http://localhost:5199"])
	response = c.get("/healthz", headers={"Origin": "http://localhost:5199"})
	assert response.headers["access-control-allow-origin"] == "http://localhost:5199"

	preflight = c.options(
		"/sessions",
		headers={
			"Origin": "http://localhost:5199",
			"Access-Control-Request-Method": "POST",
			"Access-Control-Request-Headers": "Authorization, Content-Type",
		},
	)
	assert preflight.status_code == 200

	off, _ = _client(tmp_path / "off")
	response = off.get("/healthz", headers={"Origin": "http://localhost:5199"})
	assert "access-control-allow-origin" not in response.headers
