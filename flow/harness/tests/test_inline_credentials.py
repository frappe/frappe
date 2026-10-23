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
	params = {"api_base": "http://gw.localhost"}
	for body in (
		{"api_key": KEY},
		{"api_base": "http://gw.localhost"},
		{"model_params": params},
		{"subagents": [{"name": "a", "model_params": params}]},
	):
		r = c.post("/sessions", json={"cwd": str(tmp_path), **body})
		assert r.status_code == 400, body
		assert "server policy" in r.json()["detail"], body
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	for body in ({"api_key": KEY}, {"model_params": params}):
		r = c.post(f"/sessions/{sid}/model", json={"model": "mock", **body})
		assert r.status_code == 400, body
	config = store.get(sid).config
	assert (config.api_key, config.model_params) == (None, {})


def test_inline_credentials_accepted_and_redacted(tmp_path):
	params = {"api_base": "http://gw.localhost"}
	local = _store(tmp_path / "local")
	deployed = _store(
		tmp_path / "deployed",
		tool_allowlist=DEPLOYED.tool_allowlist,
		callback_hosts=DEPLOYED.callback_hosts,
	)
	clients = [
		("inline_credentials", local, _client(local, ServerPolicy(inline_credentials=True))),
		(
			"deployed",
			deployed,
			TestClient(
				create_app(deployed, policy=DEPLOYED, auth_token="test-token"),
				headers={"Authorization": "Bearer test-token"},
			),
		),
	]
	for policy, store, c in clients:
		r = c.post(
			"/sessions",
			json={
				"cwd": str(tmp_path),
				"api_key": KEY,
				"api_base": "http://gw.localhost/v1",
				"model_params": params,
			},
		)
		assert r.status_code == 200, policy
		sid = r.json()["session_id"]
		assert r.json()["config"]["api_key"] == "***", policy
		assert r.json()["config"]["api_base"] == "http://gw.localhost/v1", policy
		assert r.json()["config"]["model_params"] == params, policy
		assert store.get(sid).config.api_key == KEY, policy
		for response in (
			r,
			c.get(f"/sessions/{sid}"),
			c.get("/sessions"),
			c.patch(f"/sessions/{sid}/config", json={"title": "renamed"}),
		):
			assert response.status_code == 200, policy
			assert KEY not in response.text, policy


def test_set_model_replaces_key_base_and_params_as_one_unit(tmp_path):
	"""Flow sends the inline fields on every switch, so a key never lands on a stale
	endpoint or with stale params."""
	store = _store(tmp_path)
	c = _client(store, ServerPolicy(inline_credentials=True))
	body = {"cwd": str(tmp_path), "api_key": KEY, "model_params": {"route": "first"}}
	sid = c.post("/sessions", json=body).json()["session_id"]
	config = store.get(sid).config

	def switch(model, **inline):
		r = c.post(f"/sessions/{sid}/model", json={"model": model, **inline})
		assert r.status_code == 200
		return r

	# a new key alone: rotation without a model change, and the old params go
	r = switch("mock", api_key="sk-second")
	assert KEY not in r.text and "sk-second" not in r.text
	assert (config.api_key, config.api_base, config.model_params) == ("sk-second", None, {})
	# the rotated key survives a restart
	assert _store(tmp_path).get(sid).config.api_key == "sk-second"

	switch("mock-b", api_key="sk-second", model_params={"route": "b"})
	assert (config.api_key, config.api_base, config.model_params) == ("sk-second", None, {"route": "b"})

	# nothing inline sent: the stored ones stay
	switch("mock")
	assert (config.api_key, config.api_base, config.model_params) == ("sk-second", None, {"route": "b"})

	# half a pair sent: all replaced
	switch("mock", api_base="http://gw.localhost")
	assert (config.api_key, config.api_base, config.model_params) == (None, "http://gw.localhost", {})

	# params alone replace the whole unit too
	switch("mock-b", model_params={"route": "c"})
	assert (config.api_key, config.api_base, config.model_params) == (None, None, {"route": "c"})

	# explicit nulls clear it
	switch("mock", api_key=None, api_base=None)
	assert (config.api_key, config.api_base, config.model_params) == (None, None, {})


def test_failed_persist_reverts_the_model_change_too(tmp_path, monkeypatch):
	"""set_model commits the model durably before the creds land in meta; a failed
	meta write must undo it, or the 500 leaves a new model on the old key."""
	store = _store(tmp_path)
	c = _client(store, ServerPolicy(inline_credentials=True))
	body = {"cwd": str(tmp_path), "api_key": KEY, "model_params": {"route": "a"}}
	sid = c.post("/sessions", json=body).json()["session_id"]
	session = store.get(sid)

	def boom(session):
		raise OSError("disk full")

	monkeypatch.setattr(store, "save_meta", boom)
	r = c.post(f"/sessions/{sid}/model", json={"model": "mock-b", "api_key": "sk-new"})
	assert r.status_code == 500
	assert session.model == "mock"
	assert (session.config.api_key, session.config.model_params) == (KEY, {"route": "a"})


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


async def test_every_model_call_carries_the_inline_credentials_and_params(tmp_path, monkeypatch):
	calls = []

	async def completion(**kwargs):
		calls.append(kwargs)
		return {"choices": [{"message": {"content": "Done"}, "finish_reason": "stop"}]}

	monkeypatch.setattr("litellm.acompletion", completion)
	session = _store(tmp_path).create(
		SessionConfig(
			cwd=str(tmp_path),
			model="openai/test",
			api_key=KEY,
			api_base="http://gw.localhost",
			model_params={"provider": {"zdr": True}},
			stream=False,
		)
	)
	handle = await session.run("hello")
	await handle.task
	await session._title_task

	assert len(calls) == 2  # the turn and the title
	for call in calls:
		assert (call["api_key"], call["api_base"], call["provider"]) == (
			KEY,
			"http://gw.localhost",
			{"zdr": True},
		)
