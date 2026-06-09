# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Tests for the python-socketio realtime server (frappe/socketio_server).

The integration tests boot the actual ASGI server on a free port (uvicorn in
a background thread) and talk to it with the python socket.io client over
real TCP, with the HTTP auth callback to the Frappe web server mocked out.
They need a reachable redis_queue and are skipped if there is none.
"""

import asyncio
import json
import os
import socket
import threading
import unittest
from unittest import mock

import redis

from frappe.socketio_server import bench_conf, redis_url
from frappe.socketio_server.auth import (
	_base_url,
	_hostname,
	_site_from_environ,
	authenticate,
	check_permission,
)
from frappe.tests import IntegrationTestCase, UnitTestCase

TEST_SITE = "sio-test-site"
TEST_USER = "socket@example.com"
VALID_SID = "valid-test-sid"
AUTH_CALLBACK_PATH = "frappe.socketio_server.auth._frappe_request"

USER_INFO = {
	"user": TEST_USER,
	"user_type": "System User",
	"installed_apps": ["frappe"],
}


def fake_frappe_request(base_url, path, *, sid=None, authorization_header=None, params=None):
	"""Stand-in for the HTTP callback to the Frappe web server."""
	if path.endswith("get_user_info"):
		if sid == VALID_SID or authorization_header:
			return {"message": USER_INFO}
		return {}
	if path.endswith("has_permission"):
		return {"message": params.get("doctype") != "Forbidden DocType"}
	return {}


def redis_available() -> bool:
	try:
		client = redis.Redis.from_url(redis_url())
		client.ping()
		client.close()
		return True
	except redis.RedisError:
		return False


class TestBenchConf(UnitTestCase):
	def test_defaults_and_env_overrides(self):
		conf = bench_conf()
		self.assertIn("socketio_port", conf)
		self.assertIn("socketio_python_port", conf)

		with mock.patch.dict(os.environ, {"FRAPPE_SOCKETIO_PORT": "9999", "FRAPPE_SITE": "envsite"}):
			conf = bench_conf()
			self.assertEqual(conf["socketio_python_port"], "9999")
			self.assertEqual(conf["default_site"], "envsite")


class TestAuthHelpers(UnitTestCase):
	def test_hostname(self):
		self.assertIsNone(_hostname(None))
		self.assertEqual(_hostname("mysite.localhost:8000"), "mysite.localhost")
		self.assertEqual(_hostname("https://mysite.com:443"), "mysite.com")
		self.assertEqual(_hostname("mysite.com"), "mysite.com")

	def test_site_from_environ(self):
		conf = {"default_site": "defsite.localhost"}
		# explicit header wins
		environ = {"HTTP_X_FRAPPE_SITE_NAME": "explicit.localhost:8000"}
		self.assertEqual(_site_from_environ(environ, conf), "explicit.localhost")
		# localhost host falls back to default_site
		environ = {"HTTP_HOST": "localhost:8000"}
		self.assertEqual(_site_from_environ(environ, conf), "defsite.localhost")
		# otherwise origin, then host
		environ = {"HTTP_HOST": "a.com:8000", "HTTP_ORIGIN": "http://b.com:8000"}
		self.assertEqual(_site_from_environ(environ, conf), "b.com")
		environ = {"HTTP_HOST": "a.com:8000"}
		self.assertEqual(_site_from_environ(environ, conf), "a.com")

	def test_base_url(self):
		environ = {"HTTP_ORIGIN": "http://mysite.localhost:8080"}
		self.assertEqual(_base_url(environ, {}), "http://mysite.localhost:8080")
		# developer_mode rewrites the port to the gunicorn worker's port
		conf = {"developer_mode": 1, "webserver_port": 8000}
		self.assertEqual(_base_url(environ, conf), "http://mysite.localhost:8000")
		# no origin: fall back to host
		environ = {"HTTP_HOST": "mysite.localhost:8000"}
		self.assertEqual(_base_url(environ, {}), "http://mysite.localhost:8000")


class TestAuthenticate(UnitTestCase):
	"""authenticate() validation and session resolution, HTTP callback mocked."""

	def _environ(self, **overrides):
		environ = {
			"HTTP_HOST": "mysite.localhost:8000",
			"HTTP_ORIGIN": "http://mysite.localhost:8000",
			"HTTP_COOKIE": f"sid={VALID_SID}",
		}
		environ.update(overrides)
		return environ

	def test_rejects_namespace_site_mismatch(self):
		ok, error = asyncio.run(authenticate(self._environ(), "/othersite.localhost"))
		self.assertFalse(ok)
		self.assertIn("Invalid namespace", error)

	def test_rejects_origin_host_mismatch(self):
		environ = self._environ(HTTP_ORIGIN="http://evil.com:8000")
		# origin determines the site, so pin it via the explicit header
		environ["HTTP_X_FRAPPE_SITE_NAME"] = "mysite.localhost"
		ok, error = asyncio.run(authenticate(environ, "/mysite.localhost"))
		self.assertFalse(ok)
		self.assertEqual(error, "Invalid origin")

	def test_rejects_missing_credentials(self):
		environ = self._environ()
		del environ["HTTP_COOKIE"]
		ok, error = asyncio.run(authenticate(environ, "/mysite.localhost"))
		self.assertFalse(ok)
		self.assertIn("Missing cookie", error)

	def test_rejects_cookie_without_sid(self):
		environ = self._environ(HTTP_COOKIE="other=value")
		ok, error = asyncio.run(authenticate(environ, "/mysite.localhost"))
		self.assertFalse(ok)
		self.assertIn("No authentication method", error)

	def test_rejects_unresolved_session(self):
		with mock.patch(AUTH_CALLBACK_PATH, return_value={}):
			ok, error = asyncio.run(authenticate(self._environ(), "/mysite.localhost"))
		self.assertFalse(ok)
		self.assertIn("Unauthorized", error)

	def test_accepts_valid_session(self):
		with mock.patch(AUTH_CALLBACK_PATH, return_value={"message": USER_INFO}) as callback:
			ok, ctx = asyncio.run(authenticate(self._environ(), "/mysite.localhost"))
		self.assertTrue(ok)
		self.assertEqual(ctx["user"], TEST_USER)
		self.assertEqual(ctx["user_type"], "System User")
		self.assertEqual(ctx["installed_apps"], ["frappe"])
		self.assertEqual(ctx["site"], "mysite.localhost")
		self.assertEqual(ctx["sid"], VALID_SID)
		callback.assert_called_once()

	def test_retries_user_info_once_for_secret_bootstrap(self):
		# first call returns {} (web worker just generated the shared secret),
		# the retry succeeds — mirrors the Node implementation
		with mock.patch(AUTH_CALLBACK_PATH, side_effect=[{}, {"message": USER_INFO}]) as callback:
			ok, ctx = asyncio.run(authenticate(self._environ(), "/mysite.localhost"))
		self.assertTrue(ok)
		self.assertEqual(ctx["user"], TEST_USER)
		self.assertEqual(callback.call_count, 2)

	def test_check_permission(self):
		ctx = {"base_url": "http://mysite.localhost:8000", "sid": VALID_SID}
		with mock.patch(AUTH_CALLBACK_PATH, return_value={"message": True}):
			self.assertTrue(asyncio.run(check_permission(ctx, "ToDo", "TODO-001")))
		with mock.patch(AUTH_CALLBACK_PATH, return_value={}):
			self.assertFalse(asyncio.run(check_permission(ctx, "ToDo", "TODO-001")))


@unittest.skipUnless(redis_available(), "redis_queue not reachable")
class TestSocketioServerIntegration(IntegrationTestCase):
	"""End-to-end: real uvicorn server, real socket.io client, real redis."""

	port: int
	_patcher = None
	_server = None
	_thread = None

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		import uvicorn

		from frappe.socketio_server.server import asgi_app

		cls._patcher = mock.patch(AUTH_CALLBACK_PATH, new=fake_frappe_request)
		cls._patcher.start()

		with socket.socket() as sock:
			sock.bind(("127.0.0.1", 0))
			cls.port = sock.getsockname()[1]

		config = uvicorn.Config(asgi_app, host="127.0.0.1", port=cls.port, lifespan="on", log_level="warning")
		cls._server = uvicorn.Server(config)
		cls._thread = threading.Thread(target=cls._server.run, daemon=True)
		cls._thread.start()

		for _ in range(100):
			if cls._server.started:
				break
			threading.Event().wait(0.1)
		else:
			raise RuntimeError("uvicorn did not start within 10s")

	@classmethod
	def tearDownClass(cls):
		cls._server.should_exit = True
		cls._thread.join(timeout=10)
		cls._patcher.stop()
		super().tearDownClass()

	@property
	def namespace(self):
		return f"/{TEST_SITE}"

	async def _connect(self, cookie=f"sid={VALID_SID}"):
		import socketio

		client = socketio.AsyncClient(reconnection=False)
		headers = {
			"Origin": f"http://127.0.0.1:{self.port}",
			"X-Frappe-Site-Name": TEST_SITE,
		}
		if cookie:
			headers["Cookie"] = cookie
		await client.connect(
			f"http://127.0.0.1:{self.port}",
			headers=headers,
			namespaces=[self.namespace],
			wait_timeout=10,
		)
		return client

	async def _publish_until(self, payload: dict, received: asyncio.Event, attempts=40):
		"""Publish to the `events` channel until the client sees it — absorbs
		subscriber startup latency in consume_events and the redis manager."""
		client = redis.Redis.from_url(redis_url())
		try:
			for _ in range(attempts):
				client.publish("events", json.dumps(payload))
				try:
					await asyncio.wait_for(received.wait(), timeout=0.5)
					return
				except TimeoutError:
					continue
			raise AssertionError(f"event never reached the client: {payload}")
		finally:
			client.close()

	def test_connect_and_ping(self):
		async def scenario():
			client = await self._connect()
			try:
				pong = asyncio.Event()
				client.on("pong", lambda *args: pong.set(), namespace=self.namespace)
				await client.emit("ping", namespace=self.namespace)
				await asyncio.wait_for(pong.wait(), timeout=10)
			finally:
				await client.disconnect()

		asyncio.run(scenario())

	def test_rejects_unauthenticated_connection(self):
		import socketio

		async def scenario():
			with self.assertRaises(socketio.exceptions.ConnectionError):
				await self._connect(cookie=None)

		asyncio.run(scenario())

	def test_rejects_invalid_session(self):
		import socketio

		async def scenario():
			with self.assertRaises(socketio.exceptions.ConnectionError):
				await self._connect(cookie="sid=bogus-sid")

		asyncio.run(scenario())

	def test_user_room_event_roundtrip(self):
		"""emit_via_redis-shaped publish reaches the user's auto-joined room."""

		async def scenario():
			client = await self._connect()
			try:
				received = asyncio.Event()
				client.on("user_event", lambda data: received.set(), namespace=self.namespace)
				await self._publish_until(
					{
						"event": "user_event",
						"message": {"hello": "world"},
						"room": f"user:{TEST_USER}",
						"namespace": TEST_SITE,
					},
					received,
				)
			finally:
				await client.disconnect()

		asyncio.run(scenario())

	def test_siteless_broadcast_reaches_namespaced_clients(self):
		"""A publish without a room (e.g. esbuild build event) must reach
		clients connected to site namespaces."""

		async def scenario():
			client = await self._connect()
			try:
				received = asyncio.Event()
				client.on("build_event", lambda data: received.set(), namespace=self.namespace)
				await self._publish_until(
					{
						"event": "build_event",
						"message": {"changed": "app.js"},
						"room": None,
						"namespace": TEST_SITE,
					},
					received,
				)
			finally:
				await client.disconnect()

		asyncio.run(scenario())

	def test_doctype_subscribe_respects_permissions(self):
		async def scenario():
			client = await self._connect()
			try:
				allowed = asyncio.Event()
				forbidden = asyncio.Event()
				client.on("allowed_event", lambda data: allowed.set(), namespace=self.namespace)
				client.on("forbidden_event", lambda data: forbidden.set(), namespace=self.namespace)

				await client.emit("doctype_subscribe", "ToDo", namespace=self.namespace)
				await client.emit("doctype_subscribe", "Forbidden DocType", namespace=self.namespace)

				# permitted doctype: event arrives
				await self._publish_until(
					{
						"event": "allowed_event",
						"message": {},
						"room": "doctype:ToDo",
						"namespace": TEST_SITE,
					},
					allowed,
				)

				# forbidden doctype: the join was denied, so the room is empty
				publisher = redis.Redis.from_url(redis_url())
				try:
					for _ in range(5):
						publisher.publish(
							"events",
							json.dumps(
								{
									"event": "forbidden_event",
									"message": {},
									"room": "doctype:Forbidden DocType",
									"namespace": TEST_SITE,
								}
							),
						)
						await asyncio.sleep(0.2)
				finally:
					publisher.close()
				self.assertFalse(forbidden.is_set())
			finally:
				await client.disconnect()

		asyncio.run(scenario())
