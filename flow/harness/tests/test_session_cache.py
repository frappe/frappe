"""The byte cap on live sessions: what it drops, what it refuses to drop, and that a
dropped session comes back whole."""

import asyncio

import pytest

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
	second = store.create(SessionConfig(model="mock", session_id="second"))
	store.get("second")  # first is now the least recently used

	store.create(SessionConfig(model="mock", session_id="third"))

	assert "first" not in store._cache
	assert "second" in store._cache
	assert "third" in store._cache
	del first, second


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


def test_a_big_session_costs_more_than_a_small_one(tmp_path):
	# room for both while they are small, but not once one carries a 150 KB log
	budget = SESSION_OVERHEAD * 2 + 100 * 1024
	store = _store(tmp_path, max_bytes=budget)
	_fill(store.create(SessionConfig(model="mock", session_id="big")), 150)
	store.create(SessionConfig(model="mock", session_id="small"))

	store = _store(tmp_path, max_bytes=budget)  # a fresh daemon charges each at its log's size
	store.get("small")
	store.get("big")

	assert "big" in store._cache
	assert "small" not in store._cache  # one heavy session is worth many light ones


def test_the_cache_never_drops_a_session_that_is_in_use(tmp_path):
	store = _store(tmp_path)
	busy = store.create(SessionConfig(model="mock", session_id="busy"))
	queue = busy.subscribe()  # a live stream is reading this session

	for index in range(6):
		store.create(SessionConfig(model="mock", session_id=f"filler{index}"))

	assert "busy" in store._cache
	busy.unsubscribe(queue)


def test_an_evicted_session_someone_holds_is_never_duplicated(tmp_path):
	"""Two objects over one log would assign the same sequence numbers twice."""
	store = _store(tmp_path)
	held = store.create(SessionConfig(model="mock", session_id="held"))
	for index in range(6):
		store.create(SessionConfig(model="mock", session_id=f"filler{index}"))
	assert "held" not in store._cache

	assert store.get("held") is held


def test_listing_sessions_does_not_promote_them(tmp_path):
	store = _store(tmp_path)
	first = store.create(SessionConfig(model="mock", session_id="first"))
	first.log.append(UserMessage(content="hi"))
	second = store.create(SessionConfig(model="mock", session_id="second"))
	second.log.append(UserMessage(content="hi"))
	store.get("second")
	del first, second

	store.list()  # reads live values off both, and must not count as using them
	store.create(SessionConfig(model="mock", session_id="third"))

	assert "first" not in store._cache


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


async def test_a_running_session_survives_a_burst(tmp_path):
	store = _store(tmp_path)
	running = store.create(SessionConfig(model="mock", session_id="running"))
	release = asyncio.Event()

	class GatedModel(MockModel):
		async def run(self, request):
			await release.wait()
			async for event in super().run(request):
				yield event

	handle = await running.run("hi", model=GatedModel(replies=[AssistantMessage(content="ok")]))
	for index in range(6):
		store.create(SessionConfig(model="mock", session_id=f"filler{index}"))

	assert "running" in store._cache

	release.set()
	await handle.task


async def test_a_run_that_grows_the_log_is_charged_when_it_settles(tmp_path):
	"""No get after the run: the settle hook alone re-costs the session and evicts."""
	store = _store(tmp_path, max_bytes=SESSION_OVERHEAD * 2 + 120 * 1024)
	small = store.create(SessionConfig(model="mock", session_id="small"))
	big = store.create(SessionConfig(model="mock", session_id="big"))

	handle = await big.run("hi", model=MockModel(replies=[AssistantMessage(content="x" * 150 * 1024)]))
	await handle.task
	await asyncio.sleep(0)  # the task's done callbacks run on the next turn

	assert "big" in store._cache
	assert "small" not in store._cache  # the grown session is now worth more than the room left
	del small, big


def test_the_last_stream_ending_lets_the_cache_drop_a_session(tmp_path):
	store = _store(tmp_path, max_bytes=SESSION_OVERHEAD // 2)  # no room for even one idle session
	busy = store.create(SessionConfig(model="mock", session_id="busy"))
	queue = busy.subscribe()
	store.get("busy")
	assert "busy" in store._cache  # held past the budget while the stream is attached

	busy.unsubscribe(queue)

	assert "busy" not in store._cache  # let go the moment the stream ended, with no further access


@pytest.mark.parametrize("budget", [0, SESSION_OVERHEAD // 2])
def test_a_budget_smaller_than_one_session_still_serves(tmp_path, budget):
	"""Nothing stays cached, and every call still answers off the log."""
	store = _store(tmp_path, max_bytes=budget)
	session = store.create(SessionConfig(model="mock", session_id="lonely"))
	session.log.append(UserMessage(content="still here"))
	del session

	assert store.get("lonely").transcript.messages[0].content == "still here"
