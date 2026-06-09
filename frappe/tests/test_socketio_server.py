# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Tests for the python-socketio realtime server (frappe/socketio_server).

Integration tests boot the real ASGI server and talk to it over TCP with
the HTTP auth callback mocked; they skip without a reachable redis_queue.
"""

import asyncio
import datetime
import json
import os
import socket
import threading
import unittest
from unittest import mock

import redis

import frappe
from frappe.socketio_server import auth as sio_auth
from frappe.socketio_server import bench_conf, redis_url
from frappe.socketio_server.auth import (
	_base_url,
	_hostname,
	_session_comfortably_fresh,
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


class TestSessionFreshness(UnitTestCase):
	"""Only sessions valid under any timezone interpretation skip HTTP."""

	def _session(self, age_seconds=0, expiry="240:00:00", **extra):
		last = datetime.datetime.now() - datetime.timedelta(seconds=age_seconds)
		return {"last_updated": str(last), "session_expiry": expiry, **extra}

	def test_fresh_session_passes(self):
		self.assertTrue(_session_comfortably_fresh(self._session()))

	def test_session_inside_tz_slack_window_falls_back(self):
		# 239h old with 240h expiry — valid locally but inside the slack window
		self.assertFalse(_session_comfortably_fresh(self._session(age_seconds=239 * 3600)))

	def test_clearly_expired_session_fails(self):
		self.assertFalse(_session_comfortably_fresh(self._session(age_seconds=480 * 3600)))

	def test_short_expiry_never_takes_fast_path(self):
		self.assertFalse(_session_comfortably_fresh(self._session(expiry="06:00:00")))

	def test_bounded_session_falls_back(self):
		self.assertFalse(_session_comfortably_fresh(self._session(session_end="2030-01-01 00:00:00+00:00")))

	def test_garbage_falls_back(self):
		self.assertFalse(_session_comfortably_fresh({}))
		self.assertFalse(_session_comfortably_fresh(self._session(expiry="soon")))
		self.assertFalse(
			_session_comfortably_fresh({"last_updated": "not a date", "session_expiry": "240:00:00"})
		)


@unittest.skipUnless(redis_available(), "redis_queue not reachable")
class TestSessionCacheFastPath(IntegrationTestCase):
	"""Fast path against the real redis session cache via frappe.cache."""

	def setUp(self):
		super().setUp()
		self.site = frappe.local.site
		self.sid = frappe.generate_hash(length=32)
		sio_auth._installed_apps_cache.clear()
		sio_auth._site_db_names.clear()

	def tearDown(self):
		frappe.cache.hdel("session", self.sid)
		sio_auth._installed_apps_cache.clear()
		sio_auth._site_db_names.clear()
		super().tearDown()

	def _put_session(self, last_updated=None, session_expiry="240:00:00", session_end=None):
		data = frappe._dict(
			{
				"user": TEST_USER,
				"sid": self.sid,
				"data": frappe._dict(
					{
						"user": TEST_USER,
						"user_type": "System User",
						"full_name": "Socket Test",
						"last_updated": last_updated or str(datetime.datetime.now()),
						"session_expiry": session_expiry,
					}
				),
			}
		)
		if session_end:
			data["data"]["session_end"] = session_end
		frappe.cache.hset("session", self.sid, data)

	def _environ(self):
		return {
			"HTTP_HOST": f"{self.site}:8000",
			"HTTP_ORIGIN": f"http://{self.site}:8000",
			"HTTP_COOKIE": f"sid={self.sid}",
		}

	def _authenticate(self):
		return asyncio.run(authenticate(self._environ(), f"/{self.site}"))

	def test_fresh_session_resolves_without_http(self):
		self._put_session()
		sio_auth._remember_installed_apps(self.site, ["frappe"])
		boom = mock.MagicMock(side_effect=AssertionError("HTTP callback must not be called"))
		with mock.patch(AUTH_CALLBACK_PATH, new=boom):
			ok, ctx = self._authenticate()
		self.assertTrue(ok)
		self.assertEqual(ctx["user"], TEST_USER)
		self.assertEqual(ctx["user_type"], "System User")
		self.assertEqual(ctx["installed_apps"], ["frappe"])

	def test_cache_miss_falls_back_to_http(self):
		sio_auth._remember_installed_apps(self.site, ["frappe"])
		with mock.patch(AUTH_CALLBACK_PATH, return_value={"message": USER_INFO}) as callback:
			ok, _ctx = self._authenticate()
		self.assertTrue(ok)
		self.assertEqual(callback.call_count, 1)

	def test_stale_session_falls_back_to_http(self):
		# expired sessions are delegated to the web server, never rejected locally
		last = str(datetime.datetime.now() - datetime.timedelta(days=20))
		self._put_session(last_updated=last)
		sio_auth._remember_installed_apps(self.site, ["frappe"])
		with mock.patch(AUTH_CALLBACK_PATH, return_value={}) as callback:
			ok, error = self._authenticate()
		self.assertFalse(ok)
		self.assertIn("Unauthorized", error)
		self.assertGreaterEqual(callback.call_count, 1)

	def test_http_resolution_primes_fast_path(self):
		self._put_session()
		with mock.patch(AUTH_CALLBACK_PATH, return_value={"message": USER_INFO}) as callback:
			ok, _ = self._authenticate()  # installed_apps unknown -> HTTP, primes cache
			self.assertTrue(ok)
			self.assertEqual(callback.call_count, 1)
			ok, ctx = self._authenticate()  # now served from redis only
			self.assertTrue(ok)
			self.assertEqual(callback.call_count, 1)
		self.assertEqual(ctx["installed_apps"], USER_INFO["installed_apps"])


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
		"""Publish to the events channel until the client sees it."""
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
