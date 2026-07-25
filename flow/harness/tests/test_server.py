import json

from fastapi.testclient import TestClient

from flow_server.model.credentials import CredentialStore
from flow_server.server import create_app
from flow_server.session.store import SessionStore


def _client(tmp_path, **store_kw):
	store_kw.setdefault(
		"credential_store",
		CredentialStore(str(tmp_path / "credentials.json")),
	)
	store = SessionStore(str(tmp_path / "data"), **store_kw)
	return TestClient(create_app(store))


def test_healthz(tmp_path):
	assert _client(tmp_path).get("/healthz").json() == {"ok": True}


def test_daemon_bearer_auth(tmp_path):
	store = SessionStore(str(tmp_path / "data"))
	c = TestClient(create_app(store, auth_token="daemon-secret"))

	assert c.get("/healthz").status_code == 200
	assert c.post("/sessions", json={"cwd": str(tmp_path)}).status_code == 401
	assert (
		c.post(
			"/sessions",
			json={"cwd": str(tmp_path)},
			headers={"Authorization": "Bearer wrong"},
		).status_code
		== 401
	)
	assert (
		c.post(
			"/sessions",
			json={"cwd": str(tmp_path)},
			headers={"Authorization": "Bearer daemon-secret"},
		).status_code
		== 200
	)


def test_create_prompt_wait_and_entries(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	# blocking prompt returns the terminal summary (Flow-like synchronous response)
	r = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hello"})
	res = r.json()
	assert res["reason"] == "done"
	assert "Mock reply" in res["output"]
	# the durable log replays the whole turn
	types = [e["type"] for e in c.get(f"/sessions/{sid}/entries").json()["entries"]]
	assert types[0] == "run_started"
	assert "user_message" in types and "assistant_message" in types
	assert types[-1] == "run_ended"


def test_run_persists_model_override(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	# A run may switch model and select a stored credential; both mock names stay offline.
	r = c.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "hi", "model": "mock/v2", "credential_id": "mock-profile"},
	)
	assert r.json()["reason"] == "done"
	cfg = c.get(f"/sessions/{sid}").json()["config"]
	assert cfg["model"] == "mock/v2"
	assert cfg["credential_id"] == "mock-profile"


def test_provider_secrets_and_endpoints_are_not_client_inputs(tmp_path):
	c = _client(tmp_path)
	for field, value in (("api_key", "secret"), ("api_base", "https://attacker.test")):
		response = c.post(
			"/sessions",
			json={"model": "mock", "cwd": str(tmp_path), field: value},
		)
		assert response.status_code == 422

	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	for field, value in (("api_key", "secret"), ("api_base", "https://attacker.test")):
		response = c.post(
			f"/sessions/{sid}/run",
			json={"message": "hello", field: value},
		)
		assert response.status_code == 422


def test_unknown_session_404(tmp_path):
	assert _client(tmp_path).get("/sessions/nope").status_code == 404


def test_resume_without_pending_errors(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	# resuming a run with nothing awaiting approval surfaces a RunError, reason "error"
	res = c.post(f"/sessions/{sid}/resume", params={"wait": "true"}, json={"answers": {}}).json()
	assert res["reason"] == "error"


def test_abort_idle(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	assert c.post(f"/sessions/{sid}/abort").json()["status"] == "idle"


def test_allowed_roots_fences_cwd(tmp_path):
	allowed = tmp_path / "allowed"
	allowed.mkdir()
	c = _client(tmp_path, allowed_roots=[str(allowed)])
	assert c.post("/sessions", json={"cwd": str(allowed / "proj")}).status_code == 200
	assert c.post("/sessions", json={"cwd": str(tmp_path / "elsewhere")}).status_code == 400


def test_rejects_path_traversal_session_id(tmp_path):
	c = _client(tmp_path)
	# a session_id that would escape the sessions dir must be rejected
	r = c.post("/sessions", json={"session_id": "../../etc/x", "cwd": str(tmp_path)})
	assert r.status_code == 400


def test_stream_replays_completed_run(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})
	with c.stream("GET", f"/sessions/{sid}/stream") as r:
		rows = [json.loads(ln[5:]) for ln in r.iter_lines() if ln.startswith("data:")]
	assert rows[-1]["type"] == "run_ended"
