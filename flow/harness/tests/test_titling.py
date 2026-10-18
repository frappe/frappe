"""Background session titling: generation, sanitization, wiring, and fallback."""

import asyncio
from types import SimpleNamespace

import pytest

from flow_harness.events import AssistantMessage, TitleChanged
from flow_harness.model.mock import MockModel
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore
from flow_harness.session.titling import generate_title


async def test_generate_title_returns_a_clean_first_line_or_none():
	cases = [
		# first message, model reply, title
		(
			"please fix the auth flow",
			AssistantMessage(content='  "Fix login bug"\nrationale'),
			"Fix login bug",
		),
		("hi", AssistantMessage(content="\n  `Refactor   store`  "), "Refactor store"),
		("hi", AssistantMessage(content="<think>hmm</think>Add retry logic"), "Add retry logic"),
		("hi", AssistantMessage(content="x" * 200), "x" * 50),
		("hi", AssistantMessage(content=" \n\t"), None),
		("   ", AssistantMessage(content="Never asked"), None),  # empty input never reaches the model
		("hello", AssistantMessage(stop_reason="error"), None),
		# a reasoning model that burns the budget thinking gets cut mid-ramble; its
		# first line must not become the session title
		(
			"create a hello world html",
			AssistantMessage(
				content="The user wants me to generate a title for a coding-agent session",
				stop_reason="length",
			),
			None,
		),
	]
	for message, reply, title in cases:
		assert await generate_title(MockModel(replies=[reply]), message) == title, reply


def _titling_session(tmp_path, monkeypatch, replies):
	store = SessionStore(str(tmp_path / "state"))
	session = store.create(SessionConfig(model="titled/model", cwd=str(tmp_path)))
	calls = []

	async def fake_auth(*_args, **_kwargs):
		return SimpleNamespace(api_key=None, base_url=None, headers={}, refresh=None)

	def fake_get_model(name, **_kwargs):
		calls.append(name)
		return MockModel(replies=list(replies))

	monkeypatch.setattr("flow_harness.session.session.resolve_model_auth", fake_auth)
	monkeypatch.setattr("flow_harness.session.session.get_model", fake_get_model)
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


async def test_a_skipped_or_failed_titling_keeps_the_fallback(tmp_path, monkeypatch):
	store = SessionStore(str(tmp_path / "state"))
	for config, title in (
		# mock sessions keep the first-message fallback; a preset title is never replaced
		(SessionConfig(model="mock", cwd=str(tmp_path)), "hello world"),
		(SessionConfig(model="titled/model", title="My session", cwd=str(tmp_path)), "My session"),
	):
		session = store.create(config)
		handle = await session.run("hello world", model=MockModel())
		await handle.task
		assert session._title_task is None, title
		assert store.title(session.id) == title

	async def failing_auth(*_args, **_kwargs):
		raise RuntimeError("no credentials")

	monkeypatch.setattr("flow_harness.session.session.resolve_model_auth", failing_auth)
	session = store.create(SessionConfig(model="titled/model", cwd=str(tmp_path)))
	handle = await session.run("fix the bug", model=MockModel())
	await handle.task
	await session._title_task
	assert session.config.title is None
	assert store.title(session.id) == "fix the bug"

	# a metadata write that fails rolls the generated title back
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


async def test_delete_cancels_in_flight_titling(tmp_path, monkeypatch):
	started = asyncio.Event()

	async def hanging_auth(*_args, **_kwargs):
		started.set()
		await asyncio.Event().wait()

	monkeypatch.setattr("flow_harness.session.session.resolve_model_auth", hanging_auth)
	store = SessionStore(str(tmp_path / "state"))
	session = store.create(SessionConfig(model="titled/model", cwd=str(tmp_path)))
	handle = await session.run("hi", model=MockModel())
	await handle.task
	await started.wait()
	store.delete(session.id)
	with pytest.raises(asyncio.CancelledError):
		await session._title_task
	assert not store.exists(session.id)
