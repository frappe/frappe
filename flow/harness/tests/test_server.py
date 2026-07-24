import json

from fastapi.testclient import TestClient

from flow_server.server import create_app
from flow_server.session.store import SessionStore


def _client(tmp_path, **store_kw):
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
	# a run may switch model (+ creds); both mock names stay offline via the mock provider
	r = c.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "hi", "model": "mock/v2", "api_base": "http://provider"},
	)
	assert r.json()["reason"] == "done"
	cfg = c.get(f"/sessions/{sid}").json()["config"]
	assert cfg["model"] == "mock/v2"
	assert cfg["api_base"] == "http://provider"


def test_api_key_override_is_never_persisted(tmp_path):
	data_dir = tmp_path / "data"
	store = SessionStore(str(data_dir))
	c = TestClient(create_app(store))
	response = c.post(
		"/sessions",
		json={"model": "mock", "cwd": str(tmp_path), "api_key": "session-secret"},
	)
	sid = response.json()["session_id"]

	assert "api_key" not in response.json()["config"]
	meta = data_dir / "sessions" / f"{sid}.meta.json"
	assert "session-secret" not in meta.read_text()
	assert oct(meta.stat().st_mode & 0o777) == "0o600"

	c.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "hello", "api_key": "run-secret"},
	)
	assert "run-secret" not in meta.read_text()


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
