"""Background session titling: generation, sanitization, wiring, and fallback."""

import asyncio
from types import SimpleNamespace

import pytest

from flow.events import AssistantMessage, TitleChanged
from flow.model.mock import MockModel
from flow.session.config import SessionConfig
from flow.session.store import SessionStore
from flow.session.titling import generate_title, sanitize_title


def test_sanitize_title_takes_first_line_unquoted_and_bounded():
	assert sanitize_title('  "Fix login bug"\nrationale') == "Fix login bug"
	assert sanitize_title("\n  `Refactor   store`  ") == "Refactor store"
	assert sanitize_title("<think>hmm</think>Add retry logic") == "Add retry logic"
	assert sanitize_title("x" * 200) == "x" * 50
	assert sanitize_title(" \n\t") is None


async def test_generate_title_uses_the_scripted_reply():
	model = MockModel(replies=[AssistantMessage(content='"Fix auth flow"')])
	assert await generate_title(model, "please fix the auth flow") == "Fix auth flow"


async def test_generate_title_rejects_empty_input_and_error_stops():
	assert await generate_title(MockModel(), "   ") is None
	model = MockModel(replies=[AssistantMessage(stop_reason="error")])
	assert await generate_title(model, "hello") is None


async def test_generate_title_rejects_truncated_reasoning():
	# a reasoning model that burns the budget thinking gets cut mid-ramble; its
	# first line must not become the session title
	model = MockModel(
		replies=[
			AssistantMessage(
				content="The user wants me to generate a title for a coding-agent session",
				stop_reason="length",
			)
		]
	)
	assert await generate_title(model, "create a hello world html") is None


def _titling_session(tmp_path, monkeypatch, replies):
	store = SessionStore(str(tmp_path / "state"))
	session = store.create(SessionConfig(model="titled/model", cwd=str(tmp_path)))
	calls = []

	async def fake_auth(*_args, **_kwargs):
		return SimpleNamespace(api_key=None, base_url=None, headers={}, refresh=None)

	def fake_get_model(name, **_kwargs):
		calls.append(name)
		return MockModel(replies=list(replies))

	monkeypatch.setattr("flow.session.session.resolve_model_auth", fake_auth)
	monkeypatch.setattr("flow.session.session.get_model", fake_get_model)
	return store, session, calls


async def test_first_run_titles_the_session_in_the_background(tmp_path, monkeypatch):
	store, session, calls = _titling_session(
		tmp_path, monkeypatch, [AssistantMessage(content="Fix login flow")]
	)
	queue = session.subscribe()
	handle = await session.run("the login page 500s", model=MockModel())
	await handle.task
	await session._title_task

	assert session.config.title == "Fix login flow"
	assert store.title(session.id) == "Fix login flow"
	events = []
	while not queue.empty():
		events.append(queue.get_nowait())
	assert any(isinstance(e, TitleChanged) and e.title == "Fix login flow" for e in events)

	# persisted: a cold store reads the stored title, and the listing prefers it
	fresh = SessionStore(str(tmp_path / "state"))
	assert fresh.title(session.id) == "Fix login flow"
	assert fresh.list()[0].title == "Fix login flow"

	# a second run never re-titles
	handle = await session.run("now add tests", model=MockModel())
	await handle.task
	assert len(calls) == 1


async def test_mock_sessions_keep_the_first_message_fallback(tmp_path):
	store = SessionStore(str(tmp_path / "state"))
	session = store.create(SessionConfig(model="mock", cwd=str(tmp_path)))
	handle = await session.run("hello world", model=MockModel())
	await handle.task
	assert session._title_task is None
	assert store.title(session.id) == "hello world"


async def test_titling_failure_leaves_the_fallback(tmp_path, monkeypatch):
	async def failing_auth(*_args, **_kwargs):
		raise RuntimeError("no credentials")

	monkeypatch.setattr("flow.session.session.resolve_model_auth", failing_auth)
	store = SessionStore(str(tmp_path / "state"))
	session = store.create(SessionConfig(model="titled/model", cwd=str(tmp_path)))
	handle = await session.run("fix the bug", model=MockModel())
	await handle.task
	await session._title_task
	assert session.config.title is None
	assert store.title(session.id) == "fix the bug"


async def test_metadata_failure_rolls_back_the_generated_title(tmp_path, monkeypatch):
	store, session, _ = _titling_session(tmp_path, monkeypatch, [AssistantMessage(content="Fix login flow")])

	def fail_to_persist(_session):
		raise OSError("disk full")

	session._persist_meta = fail_to_persist
	queue = session.subscribe()
	handle = await session.run("the login page 500s", model=MockModel())
	await handle.task
	await session._title_task

	assert session.config.title is None
	assert store.title(session.id) == "the login page 500s"
	events = []
	while not queue.empty():
		events.append(queue.get_nowait())
	assert not any(isinstance(event, TitleChanged) for event in events)
	fresh = SessionStore(str(tmp_path / "state"))
	assert fresh.title(session.id) == "the login page 500s"


async def test_client_preset_title_suppresses_generation(tmp_path):
	store = SessionStore(str(tmp_path / "state"))
	session = store.create(SessionConfig(model="titled/model", title="My session", cwd=str(tmp_path)))
	handle = await session.run("hello", model=MockModel())
	await handle.task
	assert session._title_task is None
	assert store.title(session.id) == "My session"


async def test_delete_cancels_in_flight_titling(tmp_path, monkeypatch):
	started = asyncio.Event()

	async def hanging_auth(*_args, **_kwargs):
		started.set()
		await asyncio.Event().wait()

	monkeypatch.setattr("flow.session.session.resolve_model_auth", hanging_auth)
	store = SessionStore(str(tmp_path / "state"))
	session = store.create(SessionConfig(model="titled/model", cwd=str(tmp_path)))
	handle = await session.run("hi", model=MockModel())
	await handle.task
	await started.wait()
	store.delete(session.id)
	with pytest.raises(asyncio.CancelledError):
		await session._title_task
	assert not store.exists(session.id)
