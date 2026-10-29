"""Suggested replies: one call after a finished run, on the run's own model, prompt and tools."""

import asyncio

from flow_harness.events import AssistantMessage, ToolCall
from flow_harness.model.mock import MockModel
from flow_harness.session.config import SessionConfig
from flow_harness.session.suggest_replies import REPLIES_PROMPT, parse_replies
from flow_harness.session.store import SessionStore

OFFER = AssistantMessage(
	content='{"replies": ["Show me the deals", "Add more leads"], "multi_select": false}'
)


class RecordingModel(MockModel):
	"""Keeps every request; holds the replies call until `gate` opens."""

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.requests = []
		self.gate = asyncio.Event()
		self.gate.set()

	async def run(self, request):
		self.requests.append(request)
		if request.messages[-1].content == REPLIES_PROMPT:
			await self.gate.wait()
		async for event in super().run(request):
			yield event


def _session(tmp_path, **cfg):
	events: list[dict] = []
	store = SessionStore(str(tmp_path / "data"), event_sink=lambda _sid, event: events.append(event))
	config = {"model": "scripted/model", "cwd": str(tmp_path), "suggest_replies": True, **cfg}
	session = store.create(SessionConfig(**config))
	return session, events


def _of(events, kind):
	return [event for event in events if event["type"] == kind]


async def _run(session, message, model):
	handle = await session.run(message, model=model)
	await handle.task


async def test_a_finished_run_offers_replies_from_the_whole_conversation(tmp_path):
	session, events = _session(tmp_path, tools=["read"])
	model = RecordingModel(replies=[AssistantMessage(content="Created 70 leads."), OFFER])
	await _run(session, "create demo data", model)
	await session._replies_task

	[offered] = _of(events, "replies_suggested")
	assert offered["replies"] == ["Show me the deals", "Add more leads"]
	assert offered["multi_select"] is False
	types = [event["type"] for event in events]
	assert types.index("run_ended") < types.index("replies_suggested")
	# spend outside the conversation: counted, never the context size
	[usage] = [event for event in _of(events, "usage") if event.get("purpose") == "replies"]
	assert usage["standalone"] is True

	# the run's prompt and tools, so the call reuses its cache, then the ask
	turn, ask = model.requests
	assert (ask.system_prompt, ask.tools) == (turn.system_prompt, turn.tools)
	assert ask.messages[:-1] == session.transcript.messages
	assert ask.messages[-1].content == REPLIES_PROMPT
	assert session.transcript.messages[-1].text == "Created 70 leads."


async def test_replies_come_only_after_a_finished_run_and_only_while_they_still_fit(tmp_path):
	read = AssistantMessage(content=[ToolCall(id="c1", name="read", arguments={"path": "a.txt"})])
	# switched off, a mock session, or a run that hit its turn cap: no call
	for cfg, first in (
		({"suggest_replies": False}, AssistantMessage(content="done")),
		({"model": "mock"}, AssistantMessage(content="done")),
		({"max_turns": 1}, read),
	):
		session, events = _session(tmp_path, tools=["read"], **cfg)
		model = RecordingModel(replies=[first, OFFER])
		await _run(session, "hi", model)
		assert session._replies_task is None, cfg
		assert len(model.requests) == 1

	# an answer that offers nothing usable: its spend is still counted
	unusable = (
		"Try asking about your deals.",
		'{"replies": ["Only one"]}',
		[ToolCall(id="c2", name="read", arguments={"path": "a.txt"})],
	)
	for reply in unusable:
		session, events = _session(tmp_path)
		await _run(
			session,
			"hi",
			RecordingModel(replies=[AssistantMessage(content="done"), AssistantMessage(content=reply)]),
		)
		await session._replies_task
		assert _of(events, "replies_suggested") == [], reply
		assert [event.get("purpose") for event in _of(events, "usage")] == [None, "replies"]

	# a rewind before they land: they answer the old turn, so they are dropped
	session, events = _session(tmp_path)
	model = RecordingModel(replies=[AssistantMessage(content="done"), OFFER])
	model.gate.clear()
	await _run(session, "hi", model)
	await session.rewind(0)
	model.gate.set()
	await session._replies_task
	assert _of(events, "replies_suggested") == []

	# a newer run's replies cancel the older call
	session, events = _session(tmp_path)
	model = RecordingModel(replies=[AssistantMessage(content="done"), OFFER])
	model.gate.clear()
	await _run(session, "hi", model)
	late = session._replies_task
	await _run(session, "and now?", MockModel(replies=[AssistantMessage(content="ok"), OFFER]))
	await session._replies_task
	assert late.cancelled()
	assert len(_of(events, "replies_suggested")) == 1


def test_parse_replies_takes_two_to_four_distinct_short_messages():
	fenced = '```json\n{"replies": [" Yes ", "No"], "multi_select": true}\n```'
	assert parse_replies(fenced).model_dump(include={"replies", "multi_select"}) == {
		"replies": ["Yes", "No"],
		"multi_select": True,
	}
	thought = '<think>Answer as {"replies": [...]} only.</think>\n{"replies": ["Yes", "No"]}'
	assert parse_replies(thought).replies == ["Yes", "No"]
	for text in (
		'{"replies": []}',
		'{"replies": ["a", "b", "c", "d", "e"]}',
		'{"replies": ["Yes", "Yes "]}',
		'{"replies": ["Yes", " "]}',
		'{"replies": ["Yes", "' + "x" * 201 + '"]}',
		'{"replies": "Yes"}',
		"Yes or no",
		"{not json}",
	):
		assert parse_replies(text) is None, text
