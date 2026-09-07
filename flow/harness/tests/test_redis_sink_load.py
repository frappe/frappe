import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import pytest
import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError

from flow_harness.server.redis_sink import RedisEventSink

pytestmark = pytest.mark.skipif(
	os.environ.get("FLOW_RUN_REDIS_LOAD_TESTS") != "1", reason="set FLOW_RUN_REDIS_LOAD_TESTS=1"
)


@pytest.fixture
async def redis_url():
	executable = shutil.which("redis-server")
	if executable is None:
		pytest.skip("redis-server is not installed")
	with tempfile.TemporaryDirectory(prefix="flow-load-", dir="/tmp") as directory:
		socket = str(Path(directory) / "redis.sock")
		process = subprocess.Popen(
			[executable, "--port", "0", "--unixsocket", socket, "--save", "", "--appendonly", "no"],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.STDOUT,
		)
		url = f"unix://{socket}"
		client = redis.from_url(url, socket_timeout=1)
		try:
			async with asyncio.timeout(5):
				while True:
					try:
						await client.ping()
						break
					except RedisConnectionError:
						if process.poll() is not None:
							raise RuntimeError("test Redis exited") from None
						await asyncio.sleep(0.01)
			yield url
		finally:
			try:
				await client.aclose()
			finally:
				process.terminate()
				try:
					process.wait(timeout=3)
				except subprocess.TimeoutExpired:
					process.kill()
					process.wait()


@pytest.mark.parametrize("burst", [False, True])
async def test_multi_site_redis_load(redis_url, burst):
	site_count, sessions_per_site, revisions = 8, 16, 40
	expected = site_count * sessions_per_site * revisions
	loop = asyncio.get_running_loop()
	received = defaultdict(list)
	notices = {}
	latencies = []
	client = redis.from_url(redis_url)
	try:
		async with client.pubsub() as subscription:
			await subscription.psubscribe("harness*")
			ack = await subscription.get_message(timeout=2)
			assert ack is not None and ack["type"] == "psubscribe"

			async def collect():
				async with asyncio.timeout(15):
					while True:
						message = await subscription.get_message(ignore_subscribe_messages=True, timeout=1)
						if message is None:
							continue
						event = json.loads(message["data"])
						if event["type"] == "load_complete":
							return
						if event["type"] == "resync_required":
							channel = message["channel"].decode()
							assert channel not in notices
							notices[channel] = event
							continue
						assert event["type"] == "text_delta", event
						received[event["site"], event["session_id"]].append(event["revision"])
						latencies.append(loop.time() - event["sent_at"])

			task = asyncio.create_task(collect())
			try:
				sink = RedisEventSink(redis_url)
				async with sink.lifespan(None):
					started = loop.time()
					for revision in range(revisions):
						for site in range(site_count):
							for session in range(sessions_per_site):
								sink(
									str(session),
									{
										"site": str(site),
										"type": "text_delta",
										"text": "x" * 256,
										"revision": revision,
										"stream_id": "load-test",
										"sent_at": loop.time(),
									},
								)
						if not burst:
							await asyncio.sleep(max(0, started + (revision + 1) * 0.05 - loop.time()))
				await client.publish("harness-load", '{"type":"load_complete"}')
				await task
				elapsed = loop.time() - started
			finally:
				task.cancel()
				await asyncio.gather(task, return_exceptions=True)
	finally:
		await client.aclose()
	assert len(received) == site_count * sessions_per_site
	assert all(values == list(range(8 if burst else revisions)) for values in received.values())
	assert notices == (
		{
			f"harness-resync:site:{site}": {
				"type": "resync_required",
				"session_ids": sorted(str(sid) for sid in range(sessions_per_site)),
			}
			for site in range(site_count)
		}
		if burst
		else {}
	)
	latencies.sort()
	print(
		f"burst={burst}: {len(latencies)}/{expected} events delivered, {len(latencies) / elapsed:.0f} events/s, "
		f"p99={latencies[int(len(latencies) * 0.99)] * 1000:.1f} ms, {len(notices)} resync notices"
	)
