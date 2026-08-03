import asyncio
import json
import os
import shlex
import socket

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from flow.events import AssistantMessage, ToolCall, Usage
from flow.model import Model, ModelRequest
from flow.model.credentials import CredentialStore
from flow.model.mock import MockModel
from flow.server import create_app
from flow.session.config import SessionConfig
from flow.session.store import SessionStore


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


def test_set_model_is_a_durable_entry_used_by_later_runs(tmp_path, monkeypatch):
	resolved = []

	def spy(name, **kwargs):
		resolved.append(name)
		return MockModel()

	monkeypatch.setattr("flow.agent.loop.get_model", spy)
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]

	r = c.post(f"/sessions/{sid}/model", json={"model": "mock/v2", "credential_id": "mock-profile"})
	assert r.json() == {"model": "mock/v2", "credential_id": "mock-profile"}
	assert (
		c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"}).json()["reason"]
		== "done"
	)
	assert resolved == ["mock/v2"]

	info = c.get(f"/sessions/{sid}").json()
	assert (info["model"], info["credential_id"]) == ("mock/v2", "mock-profile")
	assert info["config"]["model"] == "mock"  # the creation config is fixed
	assert c.get(f"/sessions/{sid}/entries").json()["entries"][0]["type"] == "model_changed"


def test_run_does_not_accept_model_overrides(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	r = c.post(f"/sessions/{sid}/run", json={"message": "hi", "model": "mock/v2"})
	assert r.status_code == 422  # model changes go through POST /sessions/{sid}/model


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
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: mock)
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
		replies=[AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})])]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: mock)
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
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
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
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
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
		assert cancellation is store.get(sid).abort_signal
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
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
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
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
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


async def test_stream_reconnect_with_since_continues_a_live_run(tmp_path, monkeypatch):
	# a live SSE stream needs a real server: httpx's ASGITransport buffers whole bodies
	model = _BlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)

	sock = socket.socket()
	sock.bind(("127.0.0.1", 0))
	port = sock.getsockname()[1]
	server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
	serve_task = asyncio.create_task(server.serve(sockets=[sock]))
	try:
		while not server.started:
			await asyncio.sleep(0.01)
		async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
			sid = (await client.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
			assert (await client.post(f"/sessions/{sid}/run", json={"message": "hi"})).json() == {
				"status": "started"
			}
			await asyncio.wait_for(model.started.wait(), timeout=2)

			seen = []
			async with client.stream("GET", f"/sessions/{sid}/stream") as response:
				async for line in response.aiter_lines():
					if not line.startswith("data:"):
						continue
					seen.append(json.loads(line[5:]))
					if len(seen) == 2:
						break  # drop the connection mid-run
			assert [row["type"] for row in seen] == ["run_started", "user_message"]

			model.release.set()
			for _ in range(100):
				if (await client.get(f"/sessions/{sid}")).json()["state"] == "idle":
					break
				await asyncio.sleep(0.01)
			else:
				pytest.fail("run never finished after release")

			# reconnect from the last seen cursor: the rest of the run, no duplicates
			cursor = seen[-1]["seq"]
			async with client.stream("GET", f"/sessions/{sid}/stream", params={"since": cursor}) as response:
				continued = [
					json.loads(line[5:]) async for line in response.aiter_lines() if line.startswith("data:")
				]
			assert continued[0]["seq"] == cursor + 1
			assert all(row["seq"] > cursor for row in continued)
			assert any(row["type"] == "assistant_message" for row in continued)
			assert continued[-1]["type"] == "run_ended"
	finally:
		server.should_exit = True
		await asyncio.wait_for(serve_task, timeout=5)


def test_cancel_pending_closes_a_paused_run(tmp_path, monkeypatch):
	mock = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})]),
			AssistantMessage(content="done"),
		]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
	).json()["session_id"]
	paused = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "read"}).json()
	assert paused["reason"] == "paused"

	assert c.post(f"/sessions/{sid}/cancel_pending").json() == {"status": "cancelled"}

	assert c.get(f"/sessions/{sid}").json()["state"] == "idle"
	results = [
		row for row in c.get(f"/sessions/{sid}/entries").json()["entries"] if row["type"] == "tool_result"
	]
	assert [row["tool_call_id"] for row in results] == ["c1"]
	assert all(row["is_error"] for row in results)
	# the batch is settled; a late resume has nothing left to act on
	late = c.post(
		f"/sessions/{sid}/resume",
		json={"approval_seq": paused["approval_seq"], "answers": {"c1": "Approve"}},
	)
	assert late.status_code == 409


def test_cancel_pending_without_a_pause_is_a_noop(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"cwd": str(tmp_path)}).json()["session_id"]
	assert c.post(f"/sessions/{sid}/cancel_pending").json() == {"status": "idle"}
	assert c.get(f"/sessions/{sid}/entries").json()["entries"] == []


async def test_cancel_pending_while_running_is_rejected(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (await client.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
		first = asyncio.create_task(
			client.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "go"})
		)
		await model.started.wait()

		assert (await client.post(f"/sessions/{sid}/cancel_pending")).status_code == 409

		model.release.set()
		assert (await first).json()["reason"] == "done"


def test_rewind_branches_the_conversation_over_http(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "first"})

	assert c.post(f"/sessions/{sid}/rewind", json={"target_seq": 1}).json() == {"status": "rewound"}

	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "second"})
	active = c.get(f"/sessions/{sid}/entries").json()["entries"]  # the conversation view is the default
	assert [r["content"] for r in active if r["type"] == "user_message"] == ["second"]
	everything = c.get(f"/sessions/{sid}/entries", params={"path": "all"}).json()["entries"]
	assert [r["content"] for r in everything if r["type"] == "user_message"] == ["first", "second"]
	assert "rewind" in [r["type"] for r in everything]  # the old branch is still there

	assert c.post(f"/sessions/{sid}/rewind", json={"target_seq": 999}).status_code == 409


async def test_rewind_while_running_is_rejected_over_http(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
		sid = (await client.post("/sessions", json={"cwd": str(tmp_path)})).json()["session_id"]
		first = asyncio.create_task(
			client.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "go"})
		)
		await model.started.wait()

		assert (await client.post(f"/sessions/{sid}/rewind", json={"target_seq": 1})).status_code == 409

		model.release.set()
		assert (await first).json()["reason"] == "done"


def test_active_entries_reject_a_cursor(tmp_path):
	c = _client(tmp_path)
	sid = c.post("/sessions", json={"model": "mock", "cwd": str(tmp_path)}).json()["session_id"]
	c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "hi"})

	# a rewind can retract rows before a cursor, so the snapshot view refuses one
	assert c.get(f"/sessions/{sid}/entries", params={"since": 2}).status_code == 422
	assert c.get(f"/sessions/{sid}/entries", params={"since": 2, "path": "all"}).status_code == 200
	assert c.get(f"/sessions/{sid}/entries").status_code == 200


def test_models_endpoint_lists_configured_providers_only(tmp_path, monkeypatch):
	import litellm

	from flow.model.catalog import PROVIDERS

	for provider in PROVIDERS:
		for name in provider.api_key_envs:
			monkeypatch.delenv(name, raising=False)
	monkeypatch.setattr(
		litellm,
		"model_cost",
		{
			"gpt-4o": {"mode": "chat", "supports_function_calling": True, "litellm_provider": "openai"},
			"claude-sonnet-4": {
				"mode": "chat",
				"supports_function_calling": True,
				"litellm_provider": "anthropic",
			},
			"text-embedding-3-small": {"mode": "embedding", "litellm_provider": "openai"},
		},
	)
	c = _client(tmp_path)
	assert c.get("/models").json() == {"models": []}

	monkeypatch.setenv("OPENAI_API_KEY", "k")
	assert c.get("/models").json() == {"models": [{"name": "openai/gpt-4o", "provider": "openai"}]}


def test_list_sessions_includes_cold_on_disk_sessions(tmp_path):
	c = _client(tmp_path)
	used = c.post(
		"/sessions",
		json={"model": "mock", "cwd": str(tmp_path / "a")},
	).json()["session_id"]
	fresh = c.post(
		"/sessions",
		json={"model": "mock/v2", "cwd": str(tmp_path / "b")},
	).json()["session_id"]
	c.post(f"/sessions/{used}/run", params={"wait": "true"}, json={"message": "hi"})
	latest_seq = c.get(f"/sessions/{used}").json()["latest_seq"]

	# a fresh store over the same dir caches nothing: the cold path reads meta + log tail
	for client in (c, _client(tmp_path)):
		rows = {row["session_id"]: row for row in client.get("/sessions").json()["sessions"]}
		assert rows[used] == {
			"session_id": used,
			"state": "idle",
			"model": "mock",
			"latest_seq": latest_seq,
			"cwd": str(tmp_path / "a"),
		}
		assert rows[fresh] == {
			"session_id": fresh,
			"state": "idle",
			"model": "mock/v2",
			"latest_seq": 0,
			"cwd": str(tmp_path / "b"),
		}
	# newest activity first: only `used` has log activity
	listing = _client(tmp_path).get("/sessions").json()["sessions"]
	assert [row["session_id"] for row in listing] == [used, fresh]


def test_list_sessions_reports_a_cold_paused_session(tmp_path, monkeypatch):
	(tmp_path / "a.txt").write_text("x")
	mock = MockModel(
		replies=[
			AssistantMessage(content=[ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})]),
			AssistantMessage(content="done"),
		]
	)
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: mock)
	c = _client(tmp_path)
	sid = c.post(
		"/sessions",
		json={"cwd": str(tmp_path), "confirm_tools": ["read_file"]},
	).json()["session_id"]
	paused = c.post(f"/sessions/{sid}/run", params={"wait": "true"}, json={"message": "read"}).json()
	assert paused["reason"] == "paused"

	cold = _client(tmp_path)
	(row,) = cold.get("/sessions").json()["sessions"]
	assert row["state"] == "paused"

	# resolving the batch moves the tail past run_ended(paused): the cold state follows
	c.post(
		f"/sessions/{sid}/resume",
		params={"wait": "true"},
		json={"approval_seq": paused["approval_seq"], "answers": {"c1": "Approve"}},
	)
	(row,) = _client(tmp_path).get("/sessions").json()["sessions"]
	assert row["state"] == "idle"
