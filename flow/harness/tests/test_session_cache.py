"""The byte cap on live sessions: what it drops, what it refuses to drop, and that a
dropped session comes back whole."""

import asyncio

from flow_harness.events import AssistantMessage, ToolResult, UserMessage
from flow_harness.model.mock import MockModel
from flow_harness.session.cache import SESSION_OVERHEAD, SessionCache
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore

ROOM_FOR_TWO = SESSION_OVERHEAD * 2 + 1024


def _store(tmp_path, max_bytes=ROOM_FOR_TWO):
	return SessionStore(str(tmp_path), session_cache=SessionCache(max_bytes))


def _fill(session, kilobytes):
	session.log.append(ToolResult(tool_call_id="c1", name="grep", content="x" * (kilobytes * 1024)))


def test_cache_drops_the_least_recently_used_session(tmp_path):
	store = _store(tmp_path)
	first = store.create(SessionConfig(model="mock", session_id="first"))
	first.log.append(UserMessage(content="hi"))
	second = store.create(SessionConfig(model="mock", session_id="second"))
	second.log.append(UserMessage(content="hi"))
	store.get("second")  # first is now the least recently used
	store.list()  # reads live values off both, and must not count as using them

	store.create(SessionConfig(model="mock", session_id="third"))

	assert "first" not in store._cache
	assert "second" in store._cache
	assert "third" in store._cache
	# still held here: two objects over one log would assign the same sequence numbers twice
	assert store.get("first") is first


def test_a_dropped_session_comes_back_from_its_log(tmp_path):
	store = _store(tmp_path)
	session = store.create(SessionConfig(model="mock", session_id="kept"))
	session.log.append(UserMessage(content="remember me"))
	identity = id(session)
	del session  # nothing holds it now, so eviction is free to drop the object

	for index in range(4):
		store.create(SessionConfig(model="mock", session_id=f"filler{index}"))
	assert "kept" not in store._cache

	reloaded = store.get("kept")
	assert id(reloaded) != identity
	assert reloaded.transcript.messages[0].content == "remember me"


async def test_only_a_session_in_use_outlives_the_budget(tmp_path):
	"""A live stream or a run holds a session past the budget; once it ends the session
	is let go. Nothing idle stays cached, and every call still answers off the log."""

	class GatedModel(MockModel):
		def __init__(self):
			super().__init__(replies=[AssistantMessage(content="ok")])
			self.release = asyncio.Event()

		async def run(self, request):
			await self.release.wait()
			async for event in super().run(request):
				yield event

	for budget in (0, SESSION_OVERHEAD // 2):  # no room for even one idle session
		store = _store(tmp_path / str(budget), max_bytes=budget)
		session = store.create(SessionConfig(model="mock", session_id="busy"))
		session.log.append(UserMessage(content="still here"))
		del session
		busy = store.get("busy")
		assert busy.transcript.messages[0].content == "still here", budget

		queue = busy.subscribe()  # a live stream is reading this session
		store.get("busy")
		assert "busy" in store._cache, budget
		busy.unsubscribe(queue)
		assert "busy" not in store._cache, budget  # let go the moment the stream ended

		model = GatedModel()
		handle = await busy.run("go", model=model)
		store.get("busy")
		assert "busy" in store._cache, budget  # a running session survives too
		model.release.set()
		await handle.task
		await asyncio.sleep(0)  # the task's done callbacks run on the next turn
		assert "busy" not in store._cache, budget


async def test_a_session_is_charged_for_its_log_on_load_and_when_a_run_settles(tmp_path):
	# room for two light sessions, but not beside one that carries a 150 KB log
	budget = SESSION_OVERHEAD * 2 + 120 * 1024
	store = _store(tmp_path, max_bytes=budget)
	small = store.create(SessionConfig(model="mock", session_id="small"))
	big = store.create(SessionConfig(model="mock", session_id="big"))

	handle = await big.run("hi", model=MockModel(replies=[AssistantMessage(content="x" * 150 * 1024)]))
	await handle.task
	await asyncio.sleep(0)  # the task's done callbacks run on the next turn

	# no get after the run: the settle hook alone re-costs the session and evicts
	assert "big" in store._cache
	assert "small" not in store._cache
	del small, big

	store = _store(tmp_path, max_bytes=budget)  # a fresh daemon charges each at its log's size
	store.get("small")
	store.get("big")

	assert "big" in store._cache
	assert "small" not in store._cache  # one heavy session is worth many light ones


def test_sites_share_one_budget(tmp_path):
	"""The cap is the daemon's, not each site's: a busy site pushes a quiet one out."""
	store = _store(tmp_path)
	one = store.for_site("one.localhost", allowed_roots=[str(tmp_path)])
	two = store.for_site("two.localhost", allowed_roots=[str(tmp_path)])
	quiet = one.create(SessionConfig(model="mock", session_id="quiet", cwd=str(tmp_path)))
	del quiet

	for index in range(4):
		two.create(SessionConfig(model="mock", session_id=f"busy{index}", cwd=str(tmp_path)))

	assert "quiet" not in one._cache


def test_deleting_a_session_releases_its_bytes(tmp_path):
	cache = SessionCache(ROOM_FOR_TWO)
	store = SessionStore(str(tmp_path), session_cache=cache)
	session = store.create(SessionConfig(model="mock", session_id="doomed"))
	_fill(session, 40)
	store.get("doomed")
	del session

	store.delete("doomed")

	assert cache.used_bytes == 0
	assert "doomed" not in store._cache
