import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from flow_server.events import AssistantMessage, ToolCall, Usage, _Event
from flow_server.model import Model
from flow_server.model.credentials import CredentialStore
from flow_server.model.mock import MockModel
from flow_server.server import create_app
from flow_server.session.store import SessionConfig, SessionStore


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


def test_resume_without_pending_is_rejected_without_writing_events(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	res = c.post(
		f"/sessions/{sid}/resume",
		params={"wait": "true"},
		json={"approval_seq": 1, "answers": {}},
	)
	assert res.status_code == 409
	assert c.get(f"/sessions/{sid}/entries").json()["entries"] == []


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


def test_allowed_roots_revalidate_stored_session_on_load(tmp_path):
	outside = tmp_path / "outside"
	allowed = tmp_path / "allowed"
	outside.mkdir()
	allowed.mkdir()
	data_dir = tmp_path / "data"
	first_store = SessionStore(
		str(data_dir),
		allowed_roots=[],
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	sid = first_store.create(SessionConfig(cwd=str(outside))).id

	restricted_store = SessionStore(
		str(data_dir),
		allowed_roots=[str(allowed)],
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	with pytest.raises(ValueError, match="not under an allowed root"):
		restricted_store.get(sid)


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


def test_paused_run_requires_exact_current_approval_batch(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("SECRET")
	mock = MockModel(
		replies=[
			AssistantMessage(
				tool_calls=[
					ToolCall(id="c1", name="read_file", args={"path": "a.txt"}),
					ToolCall(id="c2", name="read_file", args={"path": "a.txt"}),
				]
			),
			AssistantMessage(text="done"),
		]
	)
	monkeypatch.setattr("flow_server.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={
			"cwd": str(tmp_path),
			"confirm_tools": ["read_file"],
		},
	).json()["session_id"]

	paused = c.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read"},
	).json()
	approval_seq = paused["approval_seq"]
	assert paused["reason"] == "paused"
	assert c.get(f"/sessions/{sid}").json()["state"] == "paused"
	assert c.post(f"/sessions/{sid}/run", json={"message": "overlap"}).status_code == 409

	for payload in (
		{"approval_seq": approval_seq, "answers": {"c1": "Approve"}},
		{
			"approval_seq": approval_seq,
			"answers": {"c1": "Approve", "c2": "Approve", "extra": "Deny"},
		},
		{
			"approval_seq": approval_seq - 1,
			"answers": {"c1": "Approve", "c2": "Approve"},
		},
	):
		response = c.post(f"/sessions/{sid}/resume", json=payload)
		assert response.status_code == 409

	resumed = c.post(
		f"/sessions/{sid}/resume",
		params={"wait": "true"},
		json={
			"approval_seq": approval_seq,
			"answers": {"c1": "Approve", "c2": "Approve"},
		},
	)
	assert resumed.status_code == 200
	assert resumed.json()["reason"] == "done"
	assert c.get(f"/sessions/{sid}").json()["state"] == "idle"
	assert (
		c.post(
			f"/sessions/{sid}/resume",
			json={
				"approval_seq": approval_seq,
				"answers": {"c1": "Approve", "c2": "Approve"},
			},
		).status_code
		== 409
	)


def test_paused_state_and_approval_survive_store_reload(tmp_path, monkeypatch):
	mock = MockModel(
		replies=[
			AssistantMessage(
				tool_calls=[ToolCall(id="c1", name="read_file", args={"path": "a.txt"})]
			)
		]
	)
	monkeypatch.setattr("flow_server.agent.loop.get_model", lambda *args, **kwargs: mock)
	data_dir = tmp_path / "data"
	store = SessionStore(
		str(data_dir),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	c = TestClient(create_app(store))
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
	).json()["session_id"]
	paused = c.post(
		f"/sessions/{sid}/run",
		params={"wait": "true"},
		json={"message": "read"},
	).json()

	reloaded = SessionStore(
		str(data_dir),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	).get(sid)
	assert reloaded.state == "paused"
	assert reloaded.log.read_since(paused["approval_seq"] - 1)[0]["type"] == "approval_required"


class _BlockingModel(Model):
	name = "blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()
		self.call_count = 0

	async def run(
		self,
		messages: list[dict[str, Any]],
		tools: list[dict[str, Any]] | None = None,
		*,
		stream: bool = True,
	) -> AsyncIterator[_Event]:
		del messages, tools, stream
		self.call_count += 1
		self.started.set()
		await self.release.wait()
		yield AssistantMessage(text="done")
		yield Usage()


async def test_waiting_run_is_registered_and_concurrent_run_steers(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow_server.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
		sid = (
			await c.post(
				"/sessions",
				json={"cwd": str(tmp_path)},
			)
		).json()["session_id"]
		first = asyncio.create_task(
			c.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "first"},
			)
		)
		await model.started.wait()

		state = (await c.get(f"/sessions/{sid}")).json()
		assert state["state"] == "running"
		assert state["running"] is True
		second = await c.post(f"/sessions/{sid}/run", json={"message": "second"})
		assert second.json() == {"status": "steered"}

		model.release.set()
		assert (await first).json()["reason"] == "done"
		assert (await c.get(f"/sessions/{sid}")).json()["state"] == "idle"
		assert model.call_count == 2
		entries = (await c.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert [row["content"] for row in entries if row["type"] == "user_message"] == [
			"first",
			"second",
		]
