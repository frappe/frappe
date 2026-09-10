"""Client-managed model credentials: the policy gate, redaction, and auth precedence."""

import asyncio

from fastapi.testclient import TestClient

from flow_harness.model.auth import ResolvedModelAuth, resolve_model_auth
from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.server.policy import DEPLOYED, ServerPolicy
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore

KEY = "sk-inline-secret"


def _store(tmp_path, **store_kw) -> SessionStore:
	store_kw.setdefault("credential_store", CredentialStore(str(tmp_path / "credentials.json")))
	return SessionStore(str(tmp_path / "data"), **store_kw)


def _client(store: SessionStore, policy: ServerPolicy | None = None) -> TestClient:
	return TestClient(create_app(store, policy=policy))


def test_local_default_refuses_inline_credentials(tmp_path):
	store = _store(tmp_path)
	c = _client(store)
	for body in ({"api_key": KEY}, {"api_base": "http://gw.localhost"}):
		r = c.post("/sessions", json={"cwd": str(tmp_path), **body})
		assert r.status_code == 400
		assert "server policy" in r.json()["detail"]
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	r = c.post(f"/sessions/{sid}/model", json={"model": "mock", "api_key": KEY})
	assert r.status_code == 400
	assert store.get(sid).config.api_key is None


def test_inline_credentials_accepted_and_redacted(tmp_path):
	store = _store(tmp_path)
	c = _client(store, ServerPolicy(inline_credentials=True))
	r = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "api_key": KEY, "api_base": "http://gw.localhost/v1"},
	)
	assert r.status_code == 200
	sid = r.json()["session_id"]
	assert r.json()["config"]["api_key"] == "***"
	assert r.json()["config"]["api_base"] == "http://gw.localhost/v1"
	assert store.get(sid).config.api_key == KEY
	for response in (
		r,
		c.get(f"/sessions/{sid}"),
		c.get("/sessions"),
		c.patch(f"/sessions/{sid}/config", json={"title": "renamed"}),
	):
		assert response.status_code == 200
		assert KEY not in response.text


def test_set_model_replaces_the_inline_pair(tmp_path):
	store = _store(tmp_path)
	c = _client(store, ServerPolicy(inline_credentials=True))
	sid = c.post("/sessions", json={"cwd": str(tmp_path), "api_key": "sk-first"}).json()["session_id"]
	config = store.get(sid).config

	# same model, new key: rotation without a model change
	r = c.post(f"/sessions/{sid}/model", json={"model": "mock", "api_key": "sk-second"})
	assert r.status_code == 200
	assert KEY not in r.text and "sk-second" not in r.text
	assert (config.api_key, config.api_base) == ("sk-second", None)

	# no pair sent: the stored pair stays
	assert c.post(f"/sessions/{sid}/model", json={"model": "mock-b"}).status_code == 200
	assert config.api_key == "sk-second"

	# explicit nulls clear a previous pair (Flow sends both fields on every switch)
	r = c.post(
		f"/sessions/{sid}/model",
		json={"model": "mock", "api_key": None, "api_base": None},
	)
	assert r.status_code == 200
	assert (config.api_key, config.api_base) == (None, None)

	# half a pair sent: both replaced, so a key never lands on a stale endpoint
	r = c.post(f"/sessions/{sid}/model", json={"model": "mock", "api_base": "http://gw.localhost"})
	assert r.status_code == 200
	assert (config.api_key, config.api_base) == (None, "http://gw.localhost")


def test_failed_persist_reverts_the_model_change_too(tmp_path, monkeypatch):
	"""set_model commits the model durably before the creds land in meta; a failed
	meta write must undo it, or the 500 leaves a new model on the old key."""
	store = _store(tmp_path)
	c = _client(store, ServerPolicy(inline_credentials=True))
	sid = c.post("/sessions", json={"cwd": str(tmp_path), "api_key": KEY}).json()["session_id"]
	session = store.get(sid)

	def boom(session):
		raise OSError("disk full")

	monkeypatch.setattr(store, "save_meta", boom)
	r = c.post(f"/sessions/{sid}/model", json={"model": "mock-b", "api_key": "sk-new"})
	assert r.status_code == 500
	assert session.model == "mock"
	assert session.config.api_key == KEY


def test_inline_credentials_survive_restart(tmp_path):
	store = _store(tmp_path)
	c = _client(store, ServerPolicy(inline_credentials=True))
	sid = c.post("/sessions", json={"cwd": str(tmp_path), "api_key": KEY}).json()["session_id"]
	assert (
		c.post(f"/sessions/{sid}/model", json={"model": "mock", "api_key": "sk-rotated"}).status_code == 200
	)
	reopened = _store(tmp_path)
	assert reopened.get(sid).config.api_key == "sk-rotated"


def test_resolve_model_auth_prefers_inline(tmp_path):
	store = CredentialStore(str(tmp_path / "credentials.json"))
	store.set_api_key("anthropic", "sk-stored")

	def resolve(**kw) -> ResolvedModelAuth:
		return asyncio.run(resolve_model_auth("claude-x", store, provider_id="anthropic", **kw))

	auth = resolve(api_key=KEY, api_base="http://gw.localhost")
	assert (auth.api_key, auth.base_url) == (KEY, "http://gw.localhost")
	# an endpoint without a key still short-circuits (keyless gateways)
	auth = resolve(api_base="http://gw.localhost")
	assert (auth.api_key, auth.base_url) == (None, "http://gw.localhost")
	# nothing inline: the stored credential resolves as before
	assert resolve().api_key == "sk-stored"


def test_run_path_passes_inline_credentials(tmp_path, monkeypatch):
	from flow_harness.agent import loop

	captured = {}

	async def fake_resolve(model, store, *, provider_id=None, api_key=None, api_base=None):
		captured.update(api_key=api_key, api_base=api_base)
		return ResolvedModelAuth(api_key=api_key, base_url=api_base)

	monkeypatch.setattr(loop, "resolve_model_auth", fake_resolve)
	monkeypatch.setattr(loop, "get_model", lambda name, **kw: object())
	inputs = loop.LoopInputs(
		config=SessionConfig(cwd=str(tmp_path), api_key="sk-run", api_base="http://gw.localhost"),
		messages=[],
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
		abort=asyncio.Event(),
		model_name="mock",
	)
	asyncio.run(loop._authenticated_model(inputs))
	assert captured == {"api_key": "sk-run", "api_base": "http://gw.localhost"}


def test_deployed_accepts_inline_credentials(tmp_path):
	store = _store(tmp_path, tool_allowlist=DEPLOYED.tool_allowlist, callback_hosts=DEPLOYED.callback_hosts)
	app = create_app(store, policy=DEPLOYED, auth_token="test-token")
	c = TestClient(app, headers={"Authorization": "Bearer test-token"})
	r = c.post("/sessions", json={"cwd": str(tmp_path), "api_key": KEY})
	assert r.status_code == 200
	assert r.json()["config"]["api_key"] == "***"
	assert KEY not in r.text
