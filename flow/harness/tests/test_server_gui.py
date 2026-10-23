"""Endpoints added for the web UI: providers, fs/pick, session delete/title,
context info, and CORS."""

import asyncio

import httpx
from fastapi.testclient import TestClient

from flow_harness.model.auth import resolve_model_auth
from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.utils.fspick import PickerUnavailable
from flow_harness.session.store import SessionStore


def _client(tmp_path, **app_kw):
	store = _store(tmp_path)
	return TestClient(create_app(store, **app_kw)), store


def _store(tmp_path):
	return SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)


# --- providers --------------------------------------------------------------


def test_api_key_providers_save_list_and_remove(tmp_path):
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

	assert c.post("/providers/nope/api-key", json={"key": "x"}).status_code == 400
	assert c.post("/providers/codex/api-key", json={"key": "x"}).status_code == 400  # OAuth only
	assert c.post("/providers/openai/api-key", json={"key": ""}).status_code == 422


def test_custom_provider_lifecycle(tmp_path):
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
	keyed = {**body, "models": ["ollama/x"], "api_key": "secret"}
	gateway = c.post("/providers/custom", json=keyed).json()["provider"]["id"]
	assert gateway == "custom-local-ollama-2"

	# edit with a blank key and the same base_url: the stored key is kept
	edited = c.put(
		f"/providers/custom/{gateway}",
		json={
			"name": "Gateway",
			"base_url": "http://localhost:11434/v1/",
			"models": ["gw/m1", "gw/m1", " gw/m2 "],
		},
	).json()["provider"]
	assert edited["id"] == gateway  # the id survives a rename
	assert edited["name"] == "Gateway"
	assert edited["models"] == ["gw/m1", "gw/m2"]
	assert store.credential_store.get_custom(gateway).api_key == "secret"

	# repointing base_url with a blank key drops the key instead of leaking it
	moved = c.put(
		f"/providers/custom/{gateway}",
		json={"name": "Gateway", "base_url": "http://gw:9/v1/", "models": ["gw/m1"]},
	).json()["provider"]
	assert moved["source"] == "http://gw:9/v1"
	assert store.credential_store.get_custom(gateway).api_key is None

	# a provided key replaces the stored one
	c.put(f"/providers/custom/{gateway}", json={**keyed, "api_key": "rotated"})
	assert store.credential_store.get_custom(gateway).api_key == "rotated"

	# create-time validation applies to edits, and only custom credentials are editable
	assert c.put(f"/providers/custom/{gateway}", json={**keyed, "models": ["bare"]}).status_code == 422
	assert c.put("/providers/custom/custom-nope", json=keyed).status_code == 404
	c.post("/providers/openai/api-key", json={"key": "sk-test"})
	assert c.put("/providers/custom/openai", json=keyed).status_code == 404

	assert c.delete(f"/providers/{row['id']}").json() == {"status": "removed"}
	assert store.credential_store.get(row["id"]) is None

	base = {"name": "X", "base_url": "http://host/v1", "models": ["ollama/m"]}
	for bad in (
		{"base_url": "ftp://host"},
		{"base_url": "not-a-url"},
		# credentials in the URL would be stored in cleartext and leak via the catalog
		{"base_url": "http://u:p@host/v1"},
		# a bare id can't be routed back to this endpoint
		{"models": ["llama3.2"]},
		{"models": ["  "]},
		{"models": []},
		{"name": " "},
	):
		assert c.post("/providers/custom", json={**base, **bad}).status_code == 422, bad


async def test_oauth_flow_rejects_state_mismatch(tmp_path):
	# a single long-lived loop, like the daemon's: the flow's callback listener
	# thread must be shut down by /complete on the same loop it started on
	transport = httpx.ASGITransport(app=create_app(_store(tmp_path)))
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
		# completing without a start is a client error, as is starting a non-OAuth provider
		response = await c.post("/providers/openai/oauth/complete", json={"callback_url": "http://x?code=1"})
		assert response.status_code == 400
		assert (await c.post("/providers/openai/oauth/start")).status_code == 400


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


# --- session title / context / config / delete ------------------------------


def test_session_title_context_and_delete(tmp_path):
	c, store = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]

	detail = c.get(f"/sessions/{sid}").json()
	assert detail["title"] is None
	assert detail["context_window"] is None  # mock has no known window

	first_line = "summarize the repo"
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": first_line + "\nmore"})
	detail = c.get(f"/sessions/{sid}").json()
	assert detail["title"] == first_line
	assert detail["context_tokens"] > 0  # mock reports usage
	assert c.get("/sessions").json()["sessions"][0]["title"] == first_line

	assert c.delete(f"/sessions/{sid}").json() == {"status": "deleted"}
	assert c.get(f"/sessions/{sid}").status_code == 404
	assert c.get("/sessions").json()["sessions"] == []
	assert not store.exists(sid)
	assert c.delete(f"/sessions/{sid}").status_code == 404


def test_patch_config_persists_every_field_or_none(tmp_path, monkeypatch):
	c, store = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={
			"model": "mock",
			"cwd": str(tmp_path),
			"title": "Before",
			"tools": ["read"],
			"client_tools": [{"type": "function", "function": {"name": "old"}}],
			"confirm_tools": ["old"],
		},
	).json()["session_id"]
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
	expected = (["grep"], tools, ["new"], True, "After")
	assert (
		data["tools"],
		data["client_tools"],
		data["confirm_tools"],
		data["auto_approve"],
		data["title"],
	) == expected
	# the live session the loop's tool gate reads changed too, and a cold store sees it
	for session in (store.get(sid), _store(tmp_path).get(sid)):
		config = session.config
		assert (
			config.tools,
			config.client_tools,
			config.confirm_tools,
			config.auto_approve,
			config.title,
		) == expected
		assert set(session.server_tools) == {"grep"}

	# an empty patch changes nothing
	assert c.patch(f"/sessions/{sid}/config", json={}).json()["config"] == data
	# an invalid field is refused before anything is applied
	assert c.patch(f"/sessions/{sid}/config", json={"auto_approve": False, "title": " "}).status_code == 400
	assert store.get(sid).config.auto_approve is True
	assert c.patch(f"/sessions/{sid}/config", json={"client_tools": tools}).status_code == 400
	# unknown fields and sessions are rejected
	assert c.patch(f"/sessions/{sid}/config", json={"model": "x"}).status_code == 422
	assert c.patch(f"/sessions/{sid}/config", json={"system_prompt": "replace"}).status_code == 422
	assert c.patch("/sessions/nope/config", json={"auto_approve": True}).status_code == 404


# --- auth, web UI mount, and CORS ------------------------------------------


def test_bearer_auth_guards_the_api_but_not_the_shell_or_preflights(tmp_path):
	webui = tmp_path / "webui"
	webui.mkdir()
	(webui / "index.html").write_text("<title>Flow</title>")
	origin = "http://localhost:5199"
	c, store = _client(tmp_path, auth_token="secret", webui_dir=str(webui), cors_origins=[origin])

	# the static shell loads without a bearer; API paths still demand it
	assert "<title>Flow</title>" in c.get("/").text
	assert c.get("/healthz").status_code == 200
	for path in ("/sessions", "/providers", "/fs/file", "/skills", "/extensions/reload"):
		assert c.get(path).status_code == 401, path
	for headers in (None, {"Authorization": "Bearer wrong"}):
		assert c.post("/sessions", json={"cwd": str(tmp_path)}, headers=headers).status_code == 401
	bearer = {"Authorization": "Bearer secret"}
	assert c.get("/sessions", headers=bearer).status_code == 200
	assert c.post("/sessions", json={"cwd": str(tmp_path)}, headers=bearer).status_code == 200
	# docs would be reachable without a bearer beside the shell
	assert c.get("/openapi.json").status_code == 404
	assert c.get("/docs").status_code == 404

	# the configured origin gets CORS headers; preflights carry no Authorization
	assert c.get("/healthz", headers={"Origin": origin}).headers["access-control-allow-origin"] == origin
	preflight = c.options(
		"/sessions",
		headers={
			"Origin": origin,
			"Access-Control-Request-Method": "POST",
			"Access-Control-Request-Headers": "Authorization, Content-Type",
		},
	)
	assert preflight.status_code == 200
	assert preflight.headers["access-control-allow-origin"] == origin

	# without a webui dir, "/" stays a 404 and nothing is exempt; without origins, no CORS
	bare = TestClient(create_app(store, auth_token="secret"))
	assert bare.get("/").status_code in (401, 404)
	assert "access-control-allow-origin" not in bare.get("/healthz", headers={"Origin": origin}).headers


def test_tokenless_guard_refuses_foreign_hosts_and_origins(tmp_path):
	c = TestClient(create_app(_store(tmp_path)), base_url="http://127.0.0.1:8787")  # loopback bind

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
