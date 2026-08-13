# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Unit tests for the Python realtime server (frappe.realtime).

These exercise the contract-critical logic in isolation: auth gates, site
resolution, the handler registry + install/guest scoping, the typed Socket, the
redis->emit bridge routing, the ported core handlers (including the doc_close
fix), and publisher room mapping.

True transport/wire tests (real Socket.IO handshake, websocket upgrade, redis
reconnect against a live server + web process) are intentionally out of scope
here — they need a running realtime process, redis, and web server, and belong
in an integration run.
"""

import asyncio
import json
import os
import sys
import threading
import types
import unittest
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch


def _socketio_is_installed() -> bool:
	import importlib.util

	return importlib.util.find_spec("socketio") is not None


# Inject a minimal fake socketio so auth/dispatch import without the real dep.
# Guarded so a real install is used instead: the server tests need it.
if "socketio" not in sys.modules and not _socketio_is_installed():
	_sio_mod = types.ModuleType("socketio")
	_exc_mod = types.ModuleType("socketio.exceptions")

	class ConnectionRefusedError(Exception):
		pass

	_exc_mod.ConnectionRefusedError = ConnectionRefusedError
	_sio_mod.exceptions = _exc_mod
	sys.modules["socketio"] = _sio_mod
	sys.modules["socketio.exceptions"] = _exc_mod

import httpx

from frappe.realtime import auth as auth_mod
from frappe.realtime import bridge as bridge_mod
from frappe.realtime import dispatch as dispatch_mod
from frappe.realtime import handlers as handlers_mod
from frappe.realtime.auth import Session
from frappe.realtime.config import RealtimeConfig, get_config
from frappe.realtime.context import frappe_context
from frappe.realtime.registry import Registry
from frappe.realtime.socket import Socket, SyncSocket

ConnectionRefusedError = auth_mod.ConnectionRefusedError


def make_request(message: object = 1, record: list | None = None) -> Callable[..., Awaitable[dict]]:
	"""Stand-in for the authenticated web-process client, which is a coroutine."""

	async def request(path: str, method: str = "GET", params: dict | None = None, body: dict | None = None):
		if record is not None:
			record.append((path, method, params, threading.current_thread().name))
		return {"message": message}

	return request


def make_session(
	request: Callable[..., Awaitable[dict]] | None = None,
	data: dict | None = None,
	**identity: object,
) -> Session:
	base = {"site": "s1", "user": "a@b.com", "user_type": "System User", "installed_apps": ["frappe"]}
	base.update(identity)
	return Session(
		site=base["site"],
		user=base["user"],
		user_type=base["user_type"],
		installed_apps=base["installed_apps"],
		request=request or make_request(),
		data=data if data is not None else {},
	)


class FakeSio:
	"""In-memory stand-in for the python-socketio AsyncServer (single namespace)."""

	def __init__(self) -> None:
		self.rooms: dict[str, set[str]] = {}
		self.sessions: dict[str, Session] = {}
		self.emits: list[dict] = []
		self.manager = self

	def is_connected(self, sid: str, namespace: str | None = None) -> bool:
		return sid in self.sessions or sid in self.rooms

	async def enter_room(self, sid: str, room: str, namespace: str | None = None) -> None:
		self.rooms.setdefault(sid, set()).add(room)

	async def leave_room(self, sid: str, room: str, namespace: str | None = None) -> None:
		self.rooms.setdefault(sid, set()).discard(room)

	async def emit(
		self,
		event: str,
		data: object | None = None,
		to: str | None = None,
		room: str | None = None,
		namespace: str | None = None,
	) -> None:
		self.emits.append({"event": event, "data": data, "to": to or room, "namespace": namespace})

	async def save_session(self, sid: str, session: Session, namespace: str | None = None) -> None:
		self.sessions[sid] = session

	async def get_session(self, sid: str, namespace: str | None = None) -> Session:
		return self.sessions[sid]

	def get_participants(self, namespace: str, room: str) -> Iterator[tuple[str, str]]:
		for sid, rooms in self.rooms.items():
			if room in rooms:
				yield (sid, sid)

	def rooms_of(self, sid: str) -> set[str]:
		return self.rooms.get(sid, set())


def make_config(**overrides: object) -> RealtimeConfig:
	base = dict(port=9000, redis_queue="redis://127.0.0.1:11311", default_site=None, developer_mode=False)
	base.update(overrides)
	return RealtimeConfig(**base)


def make_environ(
	host: str | None = "s1",
	origin: str | None = "http://s1",
	cookie: str | None = "sid=abc",
	site_header: str | None = None,
	authorization: str | None = None,
) -> dict[str, str]:
	env = {}
	if host:
		env["HTTP_HOST"] = host
	if origin:
		env["HTTP_ORIGIN"] = origin
	if cookie:
		env["HTTP_COOKIE"] = cookie
	if site_header:
		env["HTTP_X_FRAPPE_SITE_NAME"] = site_header
	if authorization:
		env["HTTP_AUTHORIZATION"] = authorization
	return env


class TestAuthHelpers(unittest.TestCase):
	def test_get_hostname(self):
		self.assertEqual(auth_mod.get_hostname("http://site.local:8000"), "site.local")
		self.assertEqual(auth_mod.get_hostname("site.local:9000"), "site.local")
		self.assertEqual(auth_mod.get_hostname("site.local"), "site.local")
		self.assertIsNone(auth_mod.get_hostname(None))
		# userinfo (user:pass@host) must resolve to the real host, not the userinfo
		self.assertEqual(auth_mod.get_hostname("https://victim.com:1@evil.com"), "evil.com")
		self.assertEqual(auth_mod.get_hostname("victim.com:1@evil.com"), "evil.com")

	def test_site_resolution_order(self):
		cfg = make_config(default_site="default.local")
		# 1. X-Frappe-Site-Name wins
		env = make_environ(host="localhost", origin="http://other", site_header="chosen.local")
		self.assertEqual(auth_mod.resolve_site_name(env, cfg), "chosen.local")
		# 2. default_site only when Host is localhost/127.0.0.1
		env = make_environ(host="localhost", origin="http://other", site_header=None)
		self.assertEqual(auth_mod.resolve_site_name(env, cfg), "default.local")
		# 3. Origin hostname
		env = make_environ(host="real.host", origin="http://origin.local", site_header=None)
		self.assertEqual(auth_mod.resolve_site_name(env, make_config()), "origin.local")
		# 4. Host hostname
		env = make_environ(host="host.local", origin=None, site_header=None)
		self.assertEqual(auth_mod.resolve_site_name(env, make_config()), "host.local")

	def test_get_url_dev_mode_swaps_port(self):
		cfg = make_config(developer_mode=True, webserver_port=8000)
		self.assertEqual(auth_mod.get_url("http://x.local:9000", "/p", cfg), "http://x.local:8000/p")
		# non-dev leaves origin untouched
		self.assertEqual(
			auth_mod.get_url("http://x.local:9000", "/p", make_config()), "http://x.local:9000/p"
		)

	def test_get_url_webserver_host(self):
		# bare host gets http:// scheme and the configured port
		cfg = make_config(webserver_host="127.0.0.1", webserver_port=8000)
		self.assertEqual(auth_mod.get_url("http://x.local", "/p", cfg), "http://127.0.0.1:8000/p")
		# scheme in the value is preserved, not double-prefixed
		cfg = make_config(webserver_host="https://app.frappe.cloud", webserver_port=8000)
		self.assertEqual(auth_mod.get_url("http://x.local", "/p", cfg), "https://app.frappe.cloud:8000/p")
		# explicit port in the value is not doubled
		cfg = make_config(webserver_host="https://app.frappe.cloud:443", webserver_port=8000)
		self.assertEqual(auth_mod.get_url("http://x.local", "/p", cfg), "https://app.frappe.cloud:443/p")
		# bracketed IPv6 literal
		cfg = make_config(webserver_host="[::1]", webserver_port=8000)
		self.assertEqual(auth_mod.get_url("http://x.local", "/p", cfg), "http://[::1]:8000/p")


class TestAuthenticate(unittest.IsolatedAsyncioTestCase):
	def setUp(self):
		patcher = patch.object(auth_mod, "get_socketio_secret", new=AsyncMock(return_value="secret"))
		patcher.start()
		self.addCleanup(patcher.stop)

	def _patch_web(self, message: object):
		"""Replace the authenticated client so no HTTP is attempted."""
		return patch.object(auth_mod, "_make_request", lambda *a: make_request(message))

	def _ok_payload(self):
		return {"user": "a@b.com", "user_type": "System User", "installed_apps": ["frappe"]}

	async def test_namespace_mismatch_rejected(self):
		env = make_environ(site_header="s1")
		with self.assertRaises(ConnectionRefusedError):
			await auth_mod.authenticate(env, "/other", make_config())

	async def test_origin_mismatch_rejected(self):
		env = make_environ(host="s1", origin="http://evil", site_header="s1")
		with self.assertRaises(ConnectionRefusedError):
			await auth_mod.authenticate(env, "/s1", make_config())

	async def test_absent_origin_allowed(self):
		# Browsers omit Origin on same-origin polling, which is every embedded
		# connect. A cross-site attempt always carries one.
		env = make_environ(host="s1", origin=None, site_header="s1")
		with self._patch_web(self._ok_payload()):
			session = await auth_mod.authenticate(env, "/s1", make_config())

		self.assertEqual(session.user, "a@b.com")

	async def test_missing_host_rejected(self):
		env = make_environ(host=None, origin=None, site_header="s1")
		with self.assertRaises(ConnectionRefusedError):
			await auth_mod.authenticate(env, "/s1", make_config())

	async def test_missing_credentials_rejected(self):
		env = make_environ(site_header="s1", cookie=None, authorization=None)
		with self.assertRaises(ConnectionRefusedError):
			await auth_mod.authenticate(env, "/s1", make_config())

	async def test_empty_user_info_rejected(self):
		env = make_environ(site_header="s1")
		with self._patch_web({}), self.assertRaises(ConnectionRefusedError):
			await auth_mod.authenticate(env, "/s1", make_config())

	async def test_success_returns_session(self):
		env = make_environ(site_header="s1")
		with self._patch_web(self._ok_payload()):
			session = await auth_mod.authenticate(env, "/s1", make_config())
		self.assertEqual(session.site, "s1")
		self.assertEqual(session.user, "a@b.com")
		self.assertEqual(session.user_type, "System User")
		self.assertEqual(session.installed_apps, ["frappe"])
		self.assertTrue(callable(session.request))

	async def test_session_reuses_the_connect_time_client(self):
		# One request helper serves connect auth and every later call, so their
		# timeout / redirect / cookie handling can never diverge.
		env = make_environ(site_header="s1")
		calls = []
		with patch.object(auth_mod, "_make_request", lambda *a: make_request(self._ok_payload(), calls)):
			session = await auth_mod.authenticate(env, "/s1", make_config())
			self.assertTrue(await session.has_permission("DT", "n1"))

		self.assertEqual(
			[path for path, *_ in calls],
			[
				"/api/method/frappe.realtime.get_user_info",
				"/api/method/frappe.realtime.has_permission",
			],
		)


class TestSharedHttpClient(unittest.IsolatedAsyncioTestCase):
	"""The AsyncClient is shared by every connection, so it must stay stateless."""

	def setUp(self):
		patcher = patch.object(auth_mod, "_http_client", None)
		patcher.start()
		self.addCleanup(patcher.stop)

	async def asyncTearDown(self):
		await auth_mod.close_clients()

	def _client(self, handle: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
		client = auth_mod.get_http_client()
		# Swap only the transport; the rest is the production configuration.
		client._transport = httpx.MockTransport(handle)
		return client

	async def test_response_cookies_are_never_replayed(self):
		sent = []

		def handle(request: httpx.Request) -> httpx.Response:
			sent.append(request.headers.get("cookie"))
			return httpx.Response(200, headers={"set-cookie": "sid=user_a; Path=/"}, json={})

		client = self._client(handle)
		await client.get("http://web/api/method/x", headers={"Cookie": "sid=user_a"})
		# A token-authenticated connect must not inherit the previous user's session.
		await client.get("http://web/api/method/x", headers={"Authorization": "token key:secret"})

		self.assertEqual(sent, ["sid=user_a", None])
		self.assertEqual(len(client.cookies.jar), 0)

	def _web_request(self, handle: Callable[[httpx.Request], httpx.Response]):
		"""The production request helper, pointed at a mock transport."""
		self._client(handle)
		return auth_mod._make_request(
			make_environ(site_header="s1"),
			auth_mod.Credentials(sid="abc"),
			make_config(),
			"s1",
			"shared-secret",
		)

	async def test_redirects_are_followed(self):
		def handle(request: httpx.Request) -> httpx.Response:
			if request.url.path == "/api/method/x":
				return httpx.Response(302, headers={"location": "http://s1/final"})
			return httpx.Response(200, json={"message": {"user": "a@b.com"}})

		body = await self._web_request(handle)("/api/method/x")
		self.assertEqual(body["message"]["user"], "a@b.com")

	async def test_request_carries_credential_site_and_secret(self):
		seen = {}

		def handle(request: httpx.Request) -> httpx.Response:
			seen.update(request.headers)
			seen["method"] = request.method
			seen["query"] = request.url.params.get("doctype")
			return httpx.Response(200, json={"message": 1})

		await self._web_request(handle)("/api/method/x", "POST", params={"doctype": "ToDo"})

		self.assertEqual(seen["method"], "POST")
		self.assertEqual(seen["query"], "ToDo")
		self.assertEqual(seen["cookie"], "sid=abc")
		self.assertEqual(seen["x-frappe-site-name"], "s1")
		self.assertEqual(seen["x-frappe-socket-secret"], "shared-secret")

	async def test_close_clients_drops_both(self):
		http_client, secret_client = AsyncMock(), AsyncMock()
		with (
			patch.object(auth_mod, "_http_client", http_client),
			patch.object(auth_mod, "_secret_client", secret_client),
		):
			await auth_mod.close_clients()
			self.assertIsNone(auth_mod._http_client)
			self.assertIsNone(auth_mod._secret_client)

		http_client.aclose.assert_awaited_once()
		secret_client.aclose.assert_awaited_once()


class TestLocalRequest(unittest.IsolatedAsyncioTestCase):
	"""Embedded, the web callback runs in-process instead of over loopback HTTP."""

	def setUp(self):
		patcher = patch.object(auth_mod, "get_socketio_secret", new=AsyncMock(return_value="secret"))
		patcher.start()
		self.addCleanup(patcher.stop)

	@contextmanager
	def _wsgi(self, status: str = "200 OK", payload: object = None) -> Iterator[dict]:
		"""Stand in for frappe.app.application; importing the real one is expensive."""
		seen: dict = {}

		def application(environ, start_response):
			seen.update(environ, _thread=threading.get_ident())
			body = json.dumps({"message": payload} if payload is not None else {}).encode()
			start_response(status, [("Content-Type", "application/json")])
			return [body]

		stub = types.ModuleType("frappe.app")
		stub.application = application
		with patch.dict(sys.modules, {"frappe.app": stub}), patch.object(auth_mod, "_local_client", None):
			yield seen

	def _request(self):
		return auth_mod._make_request(
			make_environ(site_header="s1"),
			auth_mod.Credentials(sid="abc"),
			make_config(embedded=True),
			"s1",
			"shared-secret",
		)

	async def test_request_carries_credential_site_secret_and_origin(self):
		with self._wsgi(payload=1) as seen:
			body = await self._request()("/api/method/x", "POST", params={"doctype": "ToDo"})

		self.assertEqual(body["message"], 1)
		self.assertEqual(seen["REQUEST_METHOD"], "POST")
		self.assertEqual(seen["PATH_INFO"], "/api/method/x")
		self.assertEqual(seen["QUERY_STRING"], "doctype=ToDo")
		self.assertEqual(seen["HTTP_COOKIE"], "sid=abc")
		self.assertEqual(seen["HTTP_X_FRAPPE_SITE_NAME"], "s1")
		self.assertEqual(seen["HTTP_X_FRAPPE_SOCKET_SECRET"], "shared-secret")
		# The web app reads Origin for site resolution, so a local call must carry it.
		self.assertEqual(seen["HTTP_ORIGIN"], "http://s1")

	async def test_error_status_raises_like_raise_for_status(self):
		with self._wsgi(status="403 FORBIDDEN"):
			with self.assertRaises(ValueError):
				await self._request()("/api/method/x")

	async def test_empty_body_is_omitted_not_sent_as_null(self):
		with self._wsgi() as seen:
			await self._request()("/api/method/x")

		self.assertEqual(seen.get("CONTENT_LENGTH") or "0", "0")

	async def test_authenticate_uses_it_end_to_end(self):
		with self._wsgi(
			payload={"user": "a@b.com", "user_type": "System User", "installed_apps": ["frappe"]}
		):
			session = await auth_mod.authenticate(
				make_environ(host="s1", origin="http://s1"), "/s1", make_config(embedded=True)
			)

		self.assertEqual(session.user, "a@b.com")
		self.assertEqual(session.site, "s1")

	async def test_it_does_not_block_the_loop(self):
		# The WSGI call is blocking; it must go to a thread or a slow request would
		# stall every other socket on the loop.
		caller = threading.get_ident()
		with self._wsgi() as seen:
			await self._request()("/api/method/x")

		self.assertNotEqual(seen["_thread"], caller)


class TestRegistry(unittest.TestCase):
	def test_on_registers_with_flags(self):
		reg = Registry()

		@reg.on("evt", frappe_context=True, allow_guest=True)
		def handler(socket: Socket) -> None:
			pass

		handlers = reg.handlers_for("evt")
		self.assertEqual(len(handlers), 1)
		self.assertTrue(handlers[0].frappe_context)
		self.assertTrue(handlers[0].allow_guest)
		self.assertEqual(handlers[0].app, "frappe")
		self.assertIs(handlers[0].fn, handler)

	def test_importing_app_tags_owner(self):
		reg = Registry()
		with reg.importing_app("myapp"):

			@reg.on("evt")
			def handler(socket: Socket) -> None:
				pass

		self.assertEqual(reg.handlers_for("evt")[0].app, "myapp")

	def test_multiple_handlers_per_event(self):
		reg = Registry()
		reg.on("evt")(lambda s: None)
		reg.on("evt")(lambda s: None)
		self.assertEqual(len(reg.handlers_for("evt")), 2)

	def test_async_handler_with_frappe_context_rejected(self):
		reg = Registry()

		async def handler(socket: Socket) -> None:
			pass

		with self.assertRaises(TypeError):
			reg.on("evt", frappe_context=True)(handler)

	def test_async_callable_object_with_frappe_context_rejected(self):
		reg = Registry()

		class Handler:
			async def __call__(self, socket: Socket) -> None:
				pass

		with self.assertRaises(TypeError):
			reg.on("evt", frappe_context=True)(Handler())


class TestSocket(unittest.IsolatedAsyncioTestCase):
	def _socket(
		self,
		sio: FakeSio | None = None,
		request: Callable[..., Awaitable[dict]] | None = None,
		data: dict | None = None,
		**identity: object,
	) -> Socket:
		sio = sio or FakeSio()
		session = make_session(request=request, data=data, **identity)
		sio.sessions["sid1"] = session
		return Socket(sio, "sid1", "/s1", session)

	def test_session_fields(self):
		s = self._socket()
		self.assertEqual(s.site, "s1")
		self.assertEqual(s.user, "a@b.com")
		self.assertEqual(s.user_type, "System User")
		self.assertEqual(s.installed_apps, ["frappe"])

	async def test_join_leave_emit(self):
		sio = FakeSio()
		s = self._socket(sio=sio)
		await s.join("room1")
		self.assertIn("room1", sio.rooms_of("sid1"))
		await s.leave("room1")
		self.assertNotIn("room1", sio.rooms_of("sid1"))
		await s.emit("e", {"x": 1})
		self.assertEqual(sio.emits[-1], {"event": "e", "data": {"x": 1}, "to": "sid1", "namespace": "/s1"})

	async def test_get_set_persists(self):
		sio = FakeSio()
		s = self._socket(sio=sio)
		self.assertEqual(s.get("missing", []), [])
		await s.set("subscribed_documents", [["DT", "n1"]])
		self.assertEqual(sio.sessions["sid1"].data["subscribed_documents"], [["DT", "n1"]])

	async def test_has_permission_http(self):
		self.assertTrue(await self._socket(request=make_request(1)).has_permission("DT", "n1"))
		self.assertFalse(await self._socket(request=make_request(0)).has_permission("DT", "n1"))

	async def test_has_permission_stays_on_the_loop(self):
		# The check is async end to end, so it must not burn a worker thread — those
		# are all held by blocking handlers under load.
		calls = []
		s = self._socket(request=make_request(1, record=calls))
		await s.has_permission("DT", "n1")
		self.assertEqual([thread for *_, thread in calls], [threading.current_thread().name])

	async def test_sync_socket_has_permission_bridges_to_loop(self):
		# A plain handler still calls it without await; the request runs on the loop.
		calls = []
		s = self._socket(request=make_request(1, record=calls))
		sync = SyncSocket(s, asyncio.get_running_loop())
		loop_thread = threading.current_thread().name

		allowed = await asyncio.to_thread(sync.has_permission, "DT", "n1")

		self.assertTrue(allowed)
		self.assertEqual([thread for *_, thread in calls], [loop_thread])

	async def test_sync_socket_bridges_to_loop(self):
		# A plain handler runs in a worker thread and drives the socket through
		# SyncSocket; the mutations must land on the loop's server state.
		sio = FakeSio()
		s = self._socket(sio=sio)
		sync = SyncSocket(s, asyncio.get_running_loop())

		def handler() -> None:
			sync.join("room1")
			sync.set("k", "v")
			sync.emit("e", {"x": 1})

		await asyncio.to_thread(handler)
		self.assertIn("room1", sio.rooms_of("sid1"))
		self.assertEqual(sio.sessions["sid1"].data["k"], "v")
		self.assertEqual(sio.emits[-1]["event"], "e")
		self.assertEqual(sync.user, "a@b.com")

	def test_sync_socket_refuses_a_closed_loop(self):
		# Shutdown must surface as an error on the worker thread, not a forever block.
		loop = asyncio.new_event_loop()
		loop.close()
		sync = SyncSocket(self._socket(), loop)
		with self.assertRaises(RuntimeError):
			sync.join("room1")


class TestDispatch(unittest.IsolatedAsyncioTestCase):
	def setUp(self):
		self.reg = Registry()
		patcher = patch.object(dispatch_mod, "realtime", self.reg)
		patcher.start()
		self.addCleanup(patcher.stop)
		self.sio = FakeSio()

	def _session(self, user: str = "a@b.com", installed_apps: tuple[str, ...] = ("frappe",)) -> Session:
		session = make_session(user=user, installed_apps=list(installed_apps))
		self.sio.sessions["sid1"] = session
		return session

	async def test_install_scoping_skips_uninstalled_app(self):
		calls = []
		with self.reg.importing_app("otherapp"):
			self.reg.on("evt")(lambda s: calls.append("ran"))
		self._session(installed_apps=("frappe",))
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, [])

	async def test_install_scoping_runs_installed_app(self):
		calls = []
		with self.reg.importing_app("otherapp"):
			self.reg.on("evt")(lambda s: calls.append("ran"))
		self._session(installed_apps=("frappe", "otherapp"))
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, ["ran"])

	async def test_guest_gate(self):
		calls = []
		self.reg.on("evt", allow_guest=False)(lambda s: calls.append("ran"))
		self._session(user="Guest")
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, [])

	async def test_guest_allowed(self):
		calls = []
		self.reg.on("evt", allow_guest=True)(lambda s: calls.append("ran"))
		self._session(user="Guest")
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, ["ran"])

	async def test_async_handler_runs_on_loop(self):
		calls = []

		async def handler(socket: Socket) -> None:
			await socket.join("room1")
			calls.append(type(socket).__name__)

		self.reg.on("evt")(handler)
		self._session()
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, ["Socket"])
		self.assertIn("room1", self.sio.rooms_of("sid1"))

	async def test_async_callable_object_runs_on_loop(self):
		seen = []

		class Handler:
			async def __call__(self, socket: Socket) -> None:
				seen.append(type(socket).__name__)

		self.reg.on("evt")(Handler())
		self._session()
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(seen, ["Socket"])

	async def test_coroutine_returned_by_a_wrapper_is_awaited(self):
		ran = []

		async def inner(socket: Socket) -> None:
			ran.append("ran")

		# An opaque decorator hides the coroutine function behind a plain wrapper.
		def wrapper(socket: Socket):
			return inner(socket)

		self.reg.on("evt")(wrapper)
		self._session()
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(ran, ["ran"])

	async def test_sync_handler_runs_in_thread(self):
		seen = []

		def handler(socket: Socket) -> None:
			socket.join("room1")
			seen.append((type(socket).__name__, threading.current_thread() is threading.main_thread()))

		self.reg.on("evt")(handler)
		self._session()
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(seen, [("SyncSocket", False)])
		self.assertIn("room1", self.sio.rooms_of("sid1"))

	async def test_frappe_context_wrap(self):
		entered = []

		@contextmanager
		def fake_ctx(site: str, user: str) -> Iterator[None]:
			entered.append((site, user))
			yield

		self.reg.on("evt", frappe_context=True)(lambda s: None)
		self._session()
		with patch.object(dispatch_mod, "frappe_context", fake_ctx):
			await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(entered, [("s1", "a@b.com")])

	async def test_handler_error_swallowed(self):
		ran = []

		def boom(s: Socket) -> None:
			raise ValueError("boom")

		self.reg.on("evt")(boom)
		self.reg.on("evt")(lambda s: ran.append("after"))
		self._session()
		# Must not raise; the second handler still runs.
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(ran, ["after"])

	async def test_passes_event_args(self):
		seen = []
		self.reg.on("evt")(lambda s, a, b: seen.append((a, b)))
		self._session()
		await dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ("x", "y"))
		self.assertEqual(seen, [("x", "y")])


class TestFrappeContext(unittest.IsolatedAsyncioTestCase):
	def test_init_rebinds_a_fresh_local(self):
		# frappe.local is a shared mutable dict behind a ContextVar; without force the
		# worker thread would mutate the loop's copy (or skip init as already done).
		frappe = MagicMock()
		with patch.dict(sys.modules, {"frappe": frappe}), frappe_context("s1", "a@b.com"):
			pass

		frappe.init.assert_called_once_with("s1", force=True)
		frappe.set_user.assert_called_once_with("a@b.com")
		frappe.db.commit.assert_called_once()
		frappe.destroy.assert_called_once()

	async def test_two_concurrent_contexts_do_not_share_local(self):
		# Two tasks each open a context. frappe.local is one mutable dict behind a
		# ContextVar; init(force=True) must rebind a fresh one per call, otherwise the
		# tasks overwrite each other's site/user (plan.md 4.4).
		frappe = MagicMock()

		async def open_context(site: str, user: str) -> None:
			with frappe_context(site, user):
				await asyncio.sleep(0)

		with patch.dict(sys.modules, {"frappe": frappe}):
			await asyncio.gather(open_context("s1", "a@b.com"), open_context("s2", "c@d.com"))

		self.assertEqual([c.args[0] for c in frappe.init.call_args_list], ["s1", "s2"])
		self.assertTrue(all(c.kwargs["force"] for c in frappe.init.call_args_list))
		self.assertEqual([c.args[0] for c in frappe.set_user.call_args_list], ["a@b.com", "c@d.com"])


class TestConfig(unittest.TestCase):
	def _config(self, **conf: object) -> RealtimeConfig:
		import frappe

		base = {"socketio_port": 9000, "redis_queue": "redis://127.0.0.1:11311"}
		base.update(conf)
		with patch.object(frappe, "get_common_site_config", return_value=base):
			return get_config(sites_path=".")

	def test_worker_threads_are_unset_by_default(self):
		# Nothing built in dispatches to a thread, so the loop's own executor stands.
		self.assertIsNone(self._config().worker_threads)

	def test_sites_path_is_absolute(self):
		# serve() changes into sites/ after the config is built, so a relative path
		# would then resolve one level too deep.
		import frappe

		with patch.object(frappe, "get_common_site_config", return_value={"socketio_port": 9000}):
			config = get_config(sites_path="sites")

		self.assertEqual(config.sites_path, os.path.abspath("sites"))

	def test_worker_threads_override(self):
		self.assertEqual(self._config(socketio_worker_threads="8").worker_threads, 8)

	def test_embedded_is_off_unless_the_backend_says_so(self):
		self.assertFalse(self._config().embedded)
		self.assertFalse(self._config(socketio_backend="python").embedded)

	def test_embedded_backend(self):
		self.assertTrue(self._config(socketio_backend="python-embedded").embedded)


class TestServerApp(unittest.IsolatedAsyncioTestCase):
	"""RealtimeServer wiring; needs the real socketio/uvicorn deps."""

	def setUp(self):
		try:
			from frappe.realtime import server as server_mod
		except Exception as exc:  # pragma: no cover - depends on the environment
			self.skipTest(f"realtime server dependencies unavailable: {exc}")
		self.server_mod = server_mod

	def test_handlers_are_loaded_before_events_are_wired(self):
		# wire() snapshots the registry, so an embedder that only builds the server
		# must still end up with every handler bound.
		order = []
		with (
			patch.object(self.server_mod, "load_handlers", lambda *a, **k: order.append("load")),
			patch.object(self.server_mod, "wire", lambda *a, **k: order.append("wire")),
		):
			self.server_mod.RealtimeServer(make_config())

		self.assertEqual(order, ["load", "wire"])

	def test_discovery_gets_the_sites_path_from_the_config(self):
		# serve() moves into sites/ before it builds the server, so a cwd-relative path
		# reads sites/sites/apps.txt there and the bench root's apps.txt when embedded.
		# Neither exists, and get_all_apps raises rather than returning nothing.
		seen = []
		with patch.object(self.server_mod, "wire", lambda *a, **k: None):
			with patch(
				"frappe.realtime.registry.discover_app_handlers",
				lambda sites_path=None: seen.append(sites_path),
			):
				self.server_mod.RealtimeServer(make_config(sites_path="/bench/sites"))

		self.assertEqual(seen, ["/bench/sites"])

	def _build(self, config: RealtimeConfig, **kwargs: object):
		with (
			patch.object(self.server_mod, "load_handlers", lambda *a, **k: None),
			patch.object(self.server_mod, "wire", lambda *a, **k: None),
		):
			return self.server_mod.RealtimeServer(config, **kwargs)

	def test_other_asgi_app_receives_non_socketio_traffic(self):
		# Embedded, this is where the Frappe WSGI app is mounted.
		sentinel = object()
		self.assertIs(self._build(make_config(), other_asgi_app=sentinel).app.other_asgi_app, sentinel)

	def test_unset_leaves_engineio_to_answer(self):
		self.assertIsNone(self._build(make_config()).app.other_asgi_app)

	async def _startup(self, config: RealtimeConfig) -> MagicMock:
		server = self._build(config)
		loop = asyncio.get_running_loop()
		with (
			patch.object(server.bridge, "start"),
			patch.object(loop, "set_default_executor") as set_executor,
		):
			await server._on_startup()
		return set_executor

	async def test_the_loop_executor_is_left_alone_by_default(self):
		# set_default_executor replaces it for the whole loop, which embedded is
		# the host's. Nothing built in dispatches to a thread, so don't touch it.
		(await self._startup(make_config())).assert_not_called()

	async def test_worker_threads_installs_a_sized_executor(self):
		set_executor = await self._startup(make_config(worker_threads=7))

		set_executor.assert_called_once()
		self.assertEqual(set_executor.call_args.args[0]._max_workers, 7)


class TestBridge(unittest.IsolatedAsyncioTestCase):
	def setUp(self):
		self.sio = MagicMock()
		self.sio.emit = AsyncMock()
		self.bridge = bridge_mod.RedisBridge(self.sio, "redis://x")

	async def test_room_emit(self):
		await self.bridge._handle(
			'{"namespace": "s1", "room": "user:a", "event": "msg", "message": {"k": 1}}'
		)
		self.sio.emit.assert_called_once_with("msg", {"k": 1}, room="user:a", namespace="/s1")

	async def test_no_room_broadcast(self):
		self.sio.manager.rooms = {"/s1": {}, "/s2": {}}
		await self.bridge._handle('{"namespace": "s1", "event": "build", "message": {"k": 1}}')
		self.assertEqual(self.sio.emit.call_count, 2)
		namespaces = {c.kwargs["namespace"] for c in self.sio.emit.call_args_list}
		self.assertEqual(namespaces, {"/s1", "/s2"})

	async def test_malformed_message_skipped(self):
		await self.bridge._handle("not json")
		await self.bridge._handle('{"no_namespace": true}')
		self.sio.emit.assert_not_called()


class TestCoreHandlers(unittest.IsolatedAsyncioTestCase):
	def _socket(
		self,
		sio: FakeSio,
		request: Callable[..., Awaitable[dict]] | None = None,
		data: dict | None = None,
		**identity: object,
	) -> Socket:
		session = make_session(request=request, data=data, **identity)
		sio.sessions["sid1"] = session
		return Socket(sio, "sid1", "/s1", session)

	async def test_ping_pong(self):
		sio = FakeSio()
		s = self._socket(sio)
		await handlers_mod.ping(s)
		self.assertEqual(sio.emits[-1]["event"], "pong")

	async def test_on_connect_joins_rooms(self):
		sio = FakeSio()
		s = self._socket(sio, user="a@b.com")
		await handlers_mod.on_connect(s)
		rooms = sio.rooms_of("sid1")
		self.assertIn("user:a@b.com", rooms)
		self.assertIn("website", rooms)
		self.assertIn("all", rooms)  # System User

	async def test_on_connect_website_user_skips_site_room(self):
		sio = FakeSio()
		s = self._socket(sio, user_type="Website User")
		await handlers_mod.on_connect(s)
		self.assertNotIn("all", sio.rooms_of("sid1"))

	async def test_doctype_subscribe_permission_gated(self):
		sio = FakeSio()
		allow = self._socket(sio, request=make_request(1))
		await handlers_mod.doctype_subscribe(allow, "ToDo")
		self.assertIn("doctype:ToDo", sio.rooms_of("sid1"))

		sio2 = FakeSio()
		deny = self._socket(sio2, request=make_request(0))
		await handlers_mod.doctype_subscribe(deny, "ToDo")
		self.assertNotIn("doctype:ToDo", sio2.rooms_of("sid1"))

	async def test_doc_close_removes_tracked_pair(self):
		# Regression for the Node bug: the pair must actually be dropped.
		sio = FakeSio()
		s = self._socket(sio, data={"subscribed_documents": [["ToDo", "n1"], ["ToDo", "n2"]]})
		await handlers_mod.doc_close(s, "ToDo", "n1")
		self.assertEqual(sio.sessions["sid1"].data["subscribed_documents"], [["ToDo", "n2"]])

	async def test_doc_viewers_emitted_for_multiple_users(self):
		sio = FakeSio()
		session_a = make_session(user="a@b.com")
		sio.sessions["sid1"] = session_a
		sio.sessions["sid2"] = make_session(user="b@b.com")
		room = handlers_mod.open_doc_room("ToDo", "n1")
		await sio.enter_room("sid1", room)
		await sio.enter_room("sid2", room)
		s = Socket(sio, "sid1", "/s1", session_a)
		await handlers_mod.notify_doc_viewers(s, "ToDo", "n1")
		emit = sio.emits[-1]
		self.assertEqual(emit["event"], "doc_viewers")
		self.assertEqual(set(emit["data"]["users"]), {"a@b.com", "b@b.com"})

	async def test_doc_viewers_silent_for_lone_self(self):
		sio = FakeSio()
		session_a = make_session(user="a@b.com")
		sio.sessions["sid1"] = session_a
		room = handlers_mod.open_doc_room("ToDo", "n1")
		await sio.enter_room("sid1", room)
		s = Socket(sio, "sid1", "/s1", session_a)
		await handlers_mod.notify_doc_viewers(s, "ToDo", "n1")
		self.assertEqual(sio.emits, [])


class TestPublisherHelpers(unittest.TestCase):
	def _patch(self):
		import frappe.realtime as rt

		return patch.object(rt, "publish_realtime")

	def test_publish_to_user(self):
		with self._patch() as mock:
			import frappe.realtime as rt

			rt.publish_to_user("a@b.com", "evt", {"x": 1})
			mock.assert_called_once_with("evt", {"x": 1}, user="a@b.com", after_commit=False)

	def test_publish_to_doc(self):
		with self._patch() as mock:
			import frappe.realtime as rt

			rt.publish_to_doc("ToDo", "n1", "evt", {"x": 1})
			mock.assert_called_once_with("evt", {"x": 1}, doctype="ToDo", docname="n1", after_commit=False)

	def test_publish_to_doctype_room(self):
		with self._patch() as mock:
			import frappe.realtime as rt

			rt.publish_to_doctype("ToDo", "evt")
			mock.assert_called_once_with("evt", None, room="doctype:ToDo", after_commit=False)

	def test_publish_task_progress(self):
		with self._patch() as mock:
			import frappe.realtime as rt

			rt.publish_task_progress("t1", {"percent": 50})
			mock.assert_called_once_with(message={"percent": 50}, task_id="t1", after_commit=False)

	def test_publish_to_website_all_room(self):
		with self._patch() as mock:
			import frappe.realtime as rt

			rt.publish_to_website("evt")
			rt.publish_to_all("evt")
			rt.publish_to_room("custom:1", "evt")
			self.assertEqual(mock.call_args_list[0].kwargs["room"], "website")
			self.assertEqual(mock.call_args_list[1].kwargs["room"], "all")
			self.assertEqual(mock.call_args_list[2].kwargs["room"], "custom:1")


if __name__ == "__main__":
	unittest.main()
