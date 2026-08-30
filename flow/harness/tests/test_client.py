"""Phase 3 client core: FlowClient (REST) and EventStream (SSE follow + reconnect)."""

import asyncio
import socket
from contextlib import asynccontextmanager

import httpx
import pytest
import uvicorn

from flow.events import AssistantMessage, Usage
from flow.model import Model, ModelRequest
from flow.model.credentials import CredentialStore
from flow.server import create_app
from flow.session.config import SessionConfig
from flow.session.store import SessionStore
from flow_tui.client import EventStream, FlowAPIError, FlowClient


def _store(tmp_path) -> SessionStore:
	return SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)


def _asgi_client(tmp_path, **app_kw) -> FlowClient:
	transport = httpx.ASGITransport(app=create_app(_store(tmp_path), **app_kw))
	return FlowClient("http://test", transport=transport)


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

	async def run(self, request: ModelRequest):
		self.started.set()
		await self.release.wait()
		yield AssistantMessage(content="done")
		yield Usage()


# --- REST over ASGITransport ----------------------------------------------


async def test_rest_roundtrip(tmp_path, monkeypatch):
	from flow.model.catalog import PROVIDERS

	# no developer API key may leak in, or /models would query providers live
	for provider in PROVIDERS:
		for name in provider.api_key_envs:
			monkeypatch.delenv(name, raising=False)
	async with _asgi_client(tmp_path) as client:
		assert await client.healthz()

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


async def test_rest_errors_carry_status_and_detail(tmp_path):
	async with _asgi_client(tmp_path) as client:
		with pytest.raises(FlowAPIError) as e:
			await client.get_session("nope")
		assert e.value.status_code == 404

		sid = await client.create_session(SessionConfig(model="mock", cwd=str(tmp_path)))
		with pytest.raises(FlowAPIError) as e:
			await client.resume(sid, approval_seq=1, answers={})
		assert e.value.status_code == 409
		assert "approval" in str(e.value.detail)


async def test_bearer_token_is_sent(tmp_path):
	transport = httpx.ASGITransport(app=create_app(_store(tmp_path), auth_token="secret"))
	async with FlowClient("http://test", transport=transport) as anonymous:
		with pytest.raises(FlowAPIError) as e:
			await anonymous.list_sessions()
		assert e.value.status_code == 401
	async with FlowClient("http://test", token="secret", transport=transport) as client:
		assert await client.list_sessions() == []


# --- live SSE over uvicorn -------------------------------------------------


async def test_follow_stream_spans_runs_and_ignores_keepalives(tmp_path, monkeypatch):
	# a fast cadence proves keepalives really flow between the runs below
	monkeypatch.setattr("flow.server.utils.sse.KEEPALIVE_SECONDS", 0.05)
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


async def test_reconnect_mid_run_resumes_from_cursor_without_duplicates(tmp_path, monkeypatch):
	model = _BlockingModel()
	monkeypatch.setattr("flow.agent.loop.get_model", lambda *args, **kwargs: model)
	app = create_app(_store(tmp_path))
	async with _live_server(app) as url, FlowClient(url) as client:
		sid = await client.create_session(SessionConfig(cwd=str(tmp_path)))
		stream = EventStream(client, sid, backoff_initial=0.05)
		events = []
		collector = asyncio.create_task(_collect(stream, events))

		await client.run(sid, "go")
		await asyncio.wait_for(model.started.wait(), timeout=5)
		await _until(lambda: any(e.type == "user_message" for e in events))

		# drop the transport mid-run; the stream must reconnect from its cursor
		assert stream._response is not None
		await stream._response.aclose()

		model.release.set()
		await _until(lambda: _ended(events) == 1)

		seqs = [e.seq for e in events if e.durable and e.seq is not None]
		assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
		assert sum(e.type == "assistant_message" for e in events) == 1

		await stream.stop()
		await asyncio.wait_for(collector, timeout=5)


async def test_stream_raises_on_http_error_instead_of_retrying(tmp_path):
	app = create_app(_store(tmp_path))
	async with _live_server(app) as url, FlowClient(url) as client:
		stream = EventStream(client, "nope")
		with pytest.raises(FlowAPIError) as e:
			async for _ in stream:
				pass
		assert e.value.status_code == 404


async def _collect(stream: EventStream, into: list) -> None:
	async for event in stream:
		into.append(event)


def _ended(events) -> int:
	return sum(e.type == "run_ended" for e in events)
