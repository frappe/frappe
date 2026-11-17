"""Phase 3 client core: FlowClient (REST) and EventStream (SSE follow + reconnect)."""

import asyncio
import socket
from contextlib import asynccontextmanager

import httpx
import pytest
import uvicorn

from flow_harness.events import AssistantMessage, TextDelta, Usage
from flow_harness.model import Model, ModelRequest
from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore
from flow_tui.client import EventStream, FlowAPIError, FlowClient
from flow_tui.client.state import ConversationState, PartialText


def _store(tmp_path) -> SessionStore:
	return SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)


@asynccontextmanager
async def _live_server(app):
	sock = socket.socket()
	sock.bind(("127.0.0.1", 0))
	port = sock.getsockname()[1]
	server = uvicorn.Server(uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=1))
	task = asyncio.create_task(server.serve(sockets=[sock]))
	try:
		while not server.started:
			await asyncio.sleep(0.01)
		yield f"http://127.0.0.1:{port}"
	finally:
		server.should_exit = True
		await asyncio.wait_for(task, timeout=5)


async def _until(predicate, timeout=5.0):
	async with asyncio.timeout(timeout):
		while not predicate():
			await asyncio.sleep(0.01)


class _BlockingModel(Model):
	name = "blocking"

	def __init__(self):
		self.started = asyncio.Event()
		self.release = asyncio.Event()
		self.suffix_sent = asyncio.Event()
		self.finish = asyncio.Event()

	async def run(self, request: ModelRequest):
		yield TextDelta(text="prefix")
		self.started.set()
		await self.release.wait()
		yield TextDelta(text=" suffix")
		self.suffix_sent.set()
		await self.finish.wait()
		yield AssistantMessage(content="prefix suffix")
		yield Usage()


# --- REST over ASGITransport ----------------------------------------------


async def test_rest_roundtrip_auth_and_errors(tmp_path, monkeypatch):
	from flow_harness.model.catalog import PROVIDERS

	# no developer API key may leak in, or /models would query providers live
	for provider in PROVIDERS:
		for name in provider.api_key_envs:
			monkeypatch.delenv(name, raising=False)
	transport = httpx.ASGITransport(app=create_app(_store(tmp_path), auth_token="secret"))
	async with FlowClient("http://test", transport=transport) as anonymous:
		with pytest.raises(FlowAPIError) as e:
			await anonymous.list_sessions()
		assert e.value.status_code == 401
	async with FlowClient("http://test", token="secret", transport=transport) as client:
		assert await client.healthz()
		assert await client.list_sessions() == []

		sid = await client.create_session(SessionConfig(model="mock", cwd=str(tmp_path)))
		result = await client.run(sid, "hello", wait=True)
		assert result["reason"] == "done"
		assert "Mock reply" in result["output"]

		info = await client.get_session(sid)
		assert info["session_id"] == sid
		assert info["state"] == "idle"
		assert info["model"] == "mock"

		rows = await client.entries(sid)
		types = [row["type"] for row in rows["entries"]]
		assert types[0] == "run_started" and types[-1] == "run_ended"
		assert rows["preview"] == []

		assert (await client.list_sessions())[0]["session_id"] == sid
		assert await client.list_models() == {"models": [], "errors": []}

		changed = await client.set_model(sid, "mock/v2", reasoning_effort="high")
		assert changed == {
			"model": "mock/v2",
			"credential_id": None,
			"reasoning_effort": "high",
			"context_window": None,
			"supports_images": False,
		}

		assert (await client.rewind(sid, rows["entries"][0]["seq"]))["status"] == "rewound"
		assert (await client.abort(sid))["status"] == "idle"
		assert (await client.cancel_pending(sid))["status"] == "idle"

		# errors carry the status and the server's detail
		with pytest.raises(FlowAPIError) as e:
			await client.get_session("nope")
		assert e.value.status_code == 404
		with pytest.raises(FlowAPIError) as e:
			await client.resume(sid, approval_seq=1, answers={})
		assert e.value.status_code == 409
		assert "approval" in str(e.value.detail)


async def test_entries_restore_an_active_preview(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	forwarded = []
	store = _store(tmp_path)
	store.event_sink = lambda _sid, event: forwarded.append(event)
	app = create_app(store)
	transport = httpx.ASGITransport(app=app)
	async with FlowClient("http://test", transport=transport) as client:
		sid = await client.create_session(SessionConfig(cwd=str(tmp_path)))
		await client.run(sid, "go")
		await model.started.wait()

		first = await client.entries(sid, path="all")
		assert [event["type"] for event in first["entries"]] == ["run_started", "user_message"]
		assert first["preview"] == [{"type": "text_delta", "text": "prefix"}]
		assert first["state"] == "running"
		assert first["running"] is True
		assert first["stream_id"] == forwarded[-1]["stream_id"]
		assert first["revision"] == forwarded[-1]["revision"]

		model.release.set()
		await model.suffix_sent.wait()
		continued = await client.entries(sid, since=first["latest_seq"], path="all")
		assert continued["entries"] == []
		assert continued["preview"] == [{"type": "text_delta", "text": "prefix suffix"}]
		assert continued["stream_id"] == first["stream_id"]
		assert continued["latest_seq"] == first["latest_seq"]
		assert continued["revision"] == first["revision"] + 1
		buffered = [event for event in forwarded if event["revision"] > first["revision"]]
		assert [event["text"] for event in buffered] == [" suffix"]
		assert first["preview"][0]["text"] + buffered[0]["text"] == "prefix suffix"

		model.finish.set()
		async with asyncio.timeout(5):
			while (await client.get_session(sid))["running"]:
				await asyncio.sleep(0.01)
		finished = await client.entries(sid, since=first["latest_seq"], path="all")
		assert finished["preview"] == []
		assert finished["entries"][-1]["type"] == "run_ended"
		assert finished["revision"] == forwarded[-1]["revision"]
		assert [event["revision"] for event in forwarded] == list(range(1, len(forwarded) + 1))
		assert all("revision" not in event for event in finished["entries"])


# --- live SSE over uvicorn -------------------------------------------------


async def test_follow_stream_spans_runs_and_raises_on_http_errors(tmp_path, monkeypatch):
	# a fast cadence proves keepalives really flow between the runs below
	monkeypatch.setattr("flow_harness.server.utils.sse.KEEPALIVE_SECONDS", 0.05)
	app = create_app(_store(tmp_path))
	async with _live_server(app) as url, FlowClient(url) as client:
		sid = await client.create_session(SessionConfig(model="mock", cwd=str(tmp_path)))
		stream = EventStream(client, sid, backoff_initial=0.05)
		events = []
		collector = asyncio.create_task(_collect(stream, events))

		await client.run(sid, "first", wait=True)
		await _until(lambda: _ended(events) == 1)
		await asyncio.sleep(0.3)  # idle across several keepalives; the connection must hold
		await client.run(sid, "second", wait=True)
		await _until(lambda: _ended(events) == 2)

		seqs = [e.seq for e in events if e.durable and e.seq is not None]
		assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))  # each durable event once
		assert [e.content for e in events if e.type == "user_message"] == ["first", "second"]

		await stream.stop()
		await asyncio.wait_for(collector, timeout=5)

		# an HTTP error status raises instead of retrying
		with pytest.raises(FlowAPIError) as e:
			async for _ in EventStream(client, "nope"):
				pass
		assert e.value.status_code == 404


async def test_reconnect_mid_run_resumes_from_cursor_without_duplicates(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow_harness.agent.loop.get_model", lambda *args, **kwargs: model)
	app = create_app(_store(tmp_path))
	async with _live_server(app) as url, FlowClient(url) as client:
		sid = await client.create_session(SessionConfig(cwd=str(tmp_path)))
		stream = EventStream(client, sid, backoff_initial=0.05)
		events = []
		state = ConversationState()

		async def collect():
			async for event in stream:
				events.append(event)
				state.apply(event)

		def partial_text():
			return "".join(part.text for part in state.partial if isinstance(part, PartialText))

		collector = asyncio.create_task(collect())

		await client.run(sid, "go")
		await asyncio.wait_for(model.started.wait(), timeout=5)
		await _until(lambda: partial_text() == "prefix")

		# drop the transport mid-run; the stream must reconnect from its cursor
		assert stream._response is not None
		await stream._response.aclose()

		model.release.set()
		await model.suffix_sent.wait()
		await _until(lambda: partial_text().endswith(" suffix"))
		partial_after_reconnect = partial_text()
		model.finish.set()
		await _until(lambda: _ended(events) == 1)

		seqs = [e.seq for e in events if e.durable and e.seq is not None]
		assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
		assert sum(e.type == "assistant_message" for e in events) == 1
		assert partial_after_reconnect == "prefix suffix"

		await stream.stop()
		await asyncio.wait_for(collector, timeout=5)


async def _collect(stream: EventStream, into: list) -> None:
	async for event in stream:
		into.append(event)


def _ended(events) -> int:
	return sum(e.type == "run_ended" for e in events)
