import asyncio
import json
import os
import shlex

import httpx
import pytest
from fastapi.testclient import TestClient

from flow_server.events import AssistantMessage, ToolCall, Usage
from flow_server.model import Model, ModelRequest
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


def test_corrupt_log_reports_where_and_spares_other_sessions(tmp_path):
	c = _client(tmp_path)
	broken = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	healthy = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	good_line = json.dumps({"seq": 1, "type": "user_message", "content": "ok"}) + "\n"
	log = tmp_path / "data" / "sessions" / f"{broken}.jsonl"
	log.write_text(good_line + '{"seq":2,"type":"bad\n')
	restarted = _client(tmp_path)  # a fresh store caches nothing

	response = restarted.get(f"/sessions/{broken}")

	assert response.status_code == 500
	detail = response.json()["detail"]
	assert detail["error"] == "session_log_corrupt"
	assert detail["line"] == 2
	assert detail["offset"] == len(good_line.encode())
	assert str(tmp_path) not in json.dumps(detail)  # never leak the on-disk path
	# one damaged session must not take the rest of the daemon down
	assert restarted.get(f"/sessions/{healthy}").status_code == 200


def test_allowed_roots_expand_home_relative_paths(tmp_path, monkeypatch):
	home = tmp_path / "home"
	(home / "projects").mkdir(parents=True)
	monkeypatch.setenv("HOME", str(home))
	c = _client(tmp_path, allowed_roots=["~/projects"])

	# the root is configured home-relative; the client addresses it absolutely
	assert c.post("/sessions", json={"cwd": str(home / "projects" / "app")}).status_code == 200
	assert c.post("/sessions", json={"cwd": str(tmp_path / "elsewhere")}).status_code == 400
	# only roots are expanded: an addressed `~` stays literal and is fenced out
	assert c.post("/sessions", json={"cwd": "~/projects/app"}).status_code == 400


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
				content=[
					ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
					ToolCall(id="c2", name="read_file", arguments={"path": "a.txt"}),
				]
			),
			AssistantMessage(content="done"),
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


def test_abort_releases_a_paused_session(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("SECRET")
	mock = MockModel(
		replies=[
			AssistantMessage(
				content=[
					ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
					ToolCall(id="c2", name="read_file", arguments={"path": "a.txt"}),
				]
			),
			AssistantMessage(content="moved on"),
		]
	)
	monkeypatch.setattr("flow_server.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
	).json()["session_id"]
	paused = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "read"}).json()
	assert paused["reason"] == "paused"

	assert c.post(f"/sessions/{sid}/abort").json() == {"status": "aborted"}

	assert c.get(f"/sessions/{sid}").json()["state"] == "idle"
	rows = c.get(f"/sessions/{sid}/entries").json()["entries"]
	answered = [r["tool_call_id"] for r in rows if r["type"] == "tool_result"]
	assert answered == ["c1", "c2"]  # every gated call answered, so nothing dangles
	assert "SECRET" not in json.dumps(rows)  # and none of them actually ran
	assert [r["reason"] for r in rows if r["type"] == "run_ended"] == ["paused", "aborted"]
	# the session is usable again without a resume
	assert (
		c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"}).json()["reason"]
		== "done"
	)


def test_abort_on_a_paused_session_is_idempotent(tmp_path, monkeypatch):
	mock = MockModel(replies=[AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={})])])
	monkeypatch.setattr("flow_server.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
	).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "read"})

	assert c.post(f"/sessions/{sid}/abort").json() == {"status": "aborted"}
	assert c.post(f"/sessions/{sid}/abort").json() == {"status": "idle"}


def test_paused_state_and_approval_survive_store_reload(tmp_path, monkeypatch):
	mock = MockModel(
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})])]
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

	async def run(self, request: ModelRequest):
		self.call_count += 1
		self.started.set()
		await self.release.wait()
		yield AssistantMessage(content="done")
		yield Usage()


class _ResumeBlockingModel(Model):
	name = "resume-blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()
		self.call_count = 0

	async def run(self, request: ModelRequest):
		self.call_count += 1
		if self.call_count == 1:
			yield AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})])
			yield Usage()
			return
		self.started.set()
		await self.release.wait()
		yield AssistantMessage(content="done")
		yield Usage()


class _AbortBlockingModel(Model):
	name = "abort-blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.cancelled = asyncio.Event()
		self.release_cleanup = asyncio.Event()
		self.request: ModelRequest | None = None

	async def run(self, request: ModelRequest):
		self.request = request
		self.started.set()
		try:
			await asyncio.Event().wait()
		finally:
			self.cancelled.set()
			await self.release_cleanup.wait()
		if False:
			yield


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


async def test_abort_interrupts_stream_clears_steering_and_returns_session_to_idle(tmp_path, monkeypatch):
	model = _AbortBlockingModel()
	monkeypatch.setattr("flow_server.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (
			await client.post(
				"/sessions",
				json={"cwd": str(tmp_path)},
			)
		).json()["session_id"]
		run_request = asyncio.create_task(
			client.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "first"},
			)
		)
		await model.started.wait()

		steered = await client.post(f"/sessions/{sid}/run", json={"message": "discard me"})
		assert steered.json() == {"status": "steered"}
		assert (await client.post(f"/sessions/{sid}/abort")).json() == {"status": "aborting"}
		await model.cancelled.wait()

		rejected = await client.post(f"/sessions/{sid}/run", json={"message": "too late"})
		assert rejected.status_code == 409
		assert rejected.json()["detail"] == "run is aborting"
		assert model.request is not None
		cancellation = model.request.cancellation
		assert cancellation is store.get(sid).abort
		assert cancellation is not None and cancellation.is_set()

		model.release_cleanup.set()
		assert (await run_request).json()["reason"] == "aborted"
		state = (await client.get(f"/sessions/{sid}")).json()
		assert state["state"] == "idle"
		assert state["running"] is False
		entries = (await client.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert [row["content"] for row in entries if row["type"] == "user_message"] == ["first"]
		assert [row["stop_reason"] for row in entries if row["type"] == "assistant_message"] == ["aborted"]
		assert [row["reason"] for row in entries if row["type"] == "run_ended"] == ["aborted"]


async def test_http_abort_kills_active_bash_process_tree_and_repairs_transcript(tmp_path, monkeypatch):
	pid_file = tmp_path / "child.pid"
	command = f'sleep 30 & child=$!; printf \'%s\\n\' "$child" > {shlex.quote(str(pid_file))}; wait "$child"'
	model = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="bash-1", name="bash", arguments={"command": command})])
		]
	)
	monkeypatch.setattr("flow_server.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (
			await client.post(
				"/sessions",
				json={"cwd": str(tmp_path), "tools": ["bash"], "auto_approve": True},
			)
		).json()["session_id"]
		run_request = asyncio.create_task(
			client.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "run the command"},
			)
		)
		for _ in range(100):
			if pid_file.exists() and pid_file.read_text().strip():
				break
			await asyncio.sleep(0.01)
		assert pid_file.exists()
		child_pid = int(pid_file.read_text().strip())

		assert (await client.post(f"/sessions/{sid}/abort")).json() == {"status": "aborting"}
		assert (await asyncio.wait_for(run_request, timeout=2)).json()["reason"] == "aborted"

		for _ in range(100):
			try:
				os.kill(child_pid, 0)
			except ProcessLookupError:
				break
			await asyncio.sleep(0.01)
		else:
			pytest.fail("Bash child process survived HTTP cancellation")

		state = (await client.get(f"/sessions/{sid}")).json()
		assert state["state"] == "idle"
		assert state["running"] is False
		entries = (await client.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert [row["stop_reason"] for row in entries if row["type"] == "assistant_message"][-1] == "aborted"
		assert [row["tool_call_id"] for row in entries if row["type"] == "tool_result"] == ["bash-1"]
		assert [row["reason"] for row in entries if row["type"] == "run_ended"] == ["aborted"]


async def test_concurrent_resume_is_rejected_before_duplicate_tool_execution(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("SECRET")
	model = _ResumeBlockingModel()
	monkeypatch.setattr("flow_server.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (
			await client.post(
				"/sessions",
				json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
			)
		).json()["session_id"]
		paused = (
			await client.post(
				f"/sessions/{sid}/run",
				params={"wait": "true"},
				json={"message": "read"},
			)
		).json()
		payload = {
			"approval_seq": paused["approval_seq"],
			"answers": {"c1": "Approve"},
		}

		first = asyncio.create_task(
			client.post(
				f"/sessions/{sid}/resume",
				params={"wait": "true"},
				json=payload,
			)
		)
		await model.started.wait()

		overlap = await client.post(f"/sessions/{sid}/resume", json=payload)
		assert overlap.status_code == 409
		assert overlap.json()["detail"] == "run is not paused"

		model.release.set()
		assert (await first).json()["reason"] == "done"
		entries = (await client.get(f"/sessions/{sid}/entries")).json()["entries"]
		assert len([row for row in entries if row["type"] == "tool_result"]) == 1
