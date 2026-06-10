# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Unit tests for the Python realtime server (frappe.realtime_py).

These exercise the contract-critical logic in isolation: auth gates, site
resolution, the handler registry + install/guest scoping, the typed Socket, the
redis->emit bridge routing, the ported core handlers (including the doc_close
fix), and publisher room mapping.

True transport/wire tests (real Socket.IO handshake, websocket upgrade, redis
reconnect against a live server + web process) are intentionally out of scope
here — they need a running realtime process, redis, and web server, and belong
in an integration run.
"""

import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

# Inject a minimal fake socketio so auth/dispatch import without the real dep.
# Guarded so a real install (CI) is used instead.
if "socketio" not in sys.modules:
	_sio_mod = types.ModuleType("socketio")
	_exc_mod = types.ModuleType("socketio.exceptions")

	class ConnectionRefusedError(Exception):
		pass

	_exc_mod.ConnectionRefusedError = ConnectionRefusedError
	_sio_mod.exceptions = _exc_mod
	sys.modules["socketio"] = _sio_mod
	sys.modules["socketio.exceptions"] = _exc_mod

from frappe.realtime_py import auth as auth_mod
from frappe.realtime_py import bridge as bridge_mod
from frappe.realtime_py import dispatch as dispatch_mod
from frappe.realtime_py import handlers as handlers_mod
from frappe.realtime_py.config import RealtimeConfig
from frappe.realtime_py.registry import Registry
from frappe.realtime_py.socket import Socket

ConnectionRefusedError = auth_mod.ConnectionRefusedError


class FakeSio:
	"""In-memory stand-in for the python-socketio Server (single namespace)."""

	def __init__(self):
		self.rooms: dict[str, set] = {}
		self.sessions: dict[str, dict] = {}
		self.emits: list[dict] = []
		self.manager = self

	def enter_room(self, sid, room, namespace=None):
		self.rooms.setdefault(sid, set()).add(room)

	def leave_room(self, sid, room, namespace=None):
		self.rooms.setdefault(sid, set()).discard(room)

	def emit(self, event, data=None, to=None, room=None, namespace=None):
		self.emits.append({"event": event, "data": data, "to": to or room, "namespace": namespace})

	def save_session(self, sid, session, namespace=None):
		self.sessions[sid] = session

	def get_session(self, sid, namespace=None):
		return self.sessions[sid]

	def get_participants(self, namespace, room):
		for sid, rooms in self.rooms.items():
			if room in rooms:
				yield (sid, sid)

	def rooms_of(self, sid):
		return self.rooms.get(sid, set())


def make_config(**overrides):
	base = dict(port=9000, redis_queue="redis://127.0.0.1:11311", default_site=None, developer_mode=False)
	base.update(overrides)
	return RealtimeConfig(**base)


def make_environ(host="s1", origin="http://s1", cookie="sid=abc", site_header=None, authorization=None):
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


class FakeResponse:
	def __init__(self, payload):
		self._payload = payload

	def raise_for_status(self):
		pass

	def json(self):
		return self._payload


class TestAuthHelpers(unittest.TestCase):
	def test_get_hostname(self):
		self.assertEqual(auth_mod.get_hostname("http://site.local:8000"), "site.local")
		self.assertEqual(auth_mod.get_hostname("site.local:9000"), "site.local")
		self.assertEqual(auth_mod.get_hostname("site.local"), "site.local")
		self.assertIsNone(auth_mod.get_hostname(None))

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
		self.assertEqual(auth_mod.get_url("http://x.local:9000", "/p", make_config()), "http://x.local:9000/p")


class TestAuthenticate(unittest.TestCase):
	def setUp(self):
		patcher = patch.object(auth_mod, "get_socketio_secret", return_value="secret")
		patcher.start()
		self.addCleanup(patcher.stop)

	def _ok_response(self):
		return FakeResponse(
			{"message": {"user": "a@b.com", "user_type": "System User", "installed_apps": ["frappe"]}}
		)

	def test_namespace_mismatch_rejected(self):
		env = make_environ(site_header="s1")
		with self.assertRaises(ConnectionRefusedError):
			auth_mod.authenticate(env, "/other", make_config())

	def test_origin_mismatch_rejected(self):
		env = make_environ(host="s1", origin="http://evil", site_header="s1")
		with self.assertRaises(ConnectionRefusedError):
			auth_mod.authenticate(env, "/s1", make_config())

	def test_missing_credentials_rejected(self):
		env = make_environ(site_header="s1", cookie=None, authorization=None)
		with self.assertRaises(ConnectionRefusedError):
			auth_mod.authenticate(env, "/s1", make_config())

	def test_empty_user_info_rejected(self):
		env = make_environ(site_header="s1")
		with patch.object(auth_mod.requests, "get", return_value=FakeResponse({"message": {}})):
			with self.assertRaises(ConnectionRefusedError):
				auth_mod.authenticate(env, "/s1", make_config())

	def test_success_returns_session(self):
		env = make_environ(site_header="s1")
		with patch.object(auth_mod.requests, "get", return_value=self._ok_response()):
			session = auth_mod.authenticate(env, "/s1", make_config())
		self.assertEqual(session["site"], "s1")
		self.assertEqual(session["user"], "a@b.com")
		self.assertEqual(session["user_type"], "System User")
		self.assertEqual(session["installed_apps"], ["frappe"])
		self.assertEqual(session["sid"], "abc")
		self.assertTrue(callable(session["_frappe_request"]))


class TestRegistry(unittest.TestCase):
	def test_on_registers_with_flags(self):
		reg = Registry()

		@reg.on("evt", frappe_context=True, allow_guest=True)
		def handler(socket):
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
			def handler(socket):
				pass

		self.assertEqual(reg.handlers_for("evt")[0].app, "myapp")

	def test_multiple_handlers_per_event(self):
		reg = Registry()
		reg.on("evt")(lambda s: None)
		reg.on("evt")(lambda s: None)
		self.assertEqual(len(reg.handlers_for("evt")), 2)


class TestSocket(unittest.TestCase):
	def _socket(self, sio=None, frappe_request=None, **session):
		sio = sio or FakeSio()
		base = {"site": "s1", "user": "a@b.com", "user_type": "System User", "installed_apps": ["frappe"]}
		base.update(session)
		sio.sessions["sid1"] = base
		return Socket(sio, "sid1", "/s1", base, frappe_request)

	def test_session_fields(self):
		s = self._socket()
		self.assertEqual(s.site, "s1")
		self.assertEqual(s.user, "a@b.com")
		self.assertEqual(s.user_type, "System User")
		self.assertEqual(s.installed_apps, ["frappe"])

	def test_join_leave_emit(self):
		sio = FakeSio()
		s = self._socket(sio=sio)
		s.join("room1")
		self.assertIn("room1", sio.rooms_of("sid1"))
		s.leave("room1")
		self.assertNotIn("room1", sio.rooms_of("sid1"))
		s.emit("e", {"x": 1})
		self.assertEqual(sio.emits[-1], {"event": "e", "data": {"x": 1}, "to": "sid1", "namespace": "/s1"})

	def test_get_set_persists(self):
		sio = FakeSio()
		s = self._socket(sio=sio)
		self.assertEqual(s.get("missing", []), [])
		s.set("subscribed_documents", [["DT", "n1"]])
		self.assertEqual(sio.sessions["sid1"]["subscribed_documents"], [["DT", "n1"]])

	def test_has_permission_http(self):
		s = self._socket(frappe_request=lambda path, args: {"message": 1})
		self.assertTrue(s.has_permission("DT", "n1"))
		s = self._socket(frappe_request=lambda path, args: {"message": 0})
		self.assertFalse(s.has_permission("DT", "n1"))


class TestDispatch(unittest.TestCase):
	def setUp(self):
		self.reg = Registry()
		patcher = patch.object(dispatch_mod, "realtime", self.reg)
		patcher.start()
		self.addCleanup(patcher.stop)
		self.sio = FakeSio()

	def _session(self, user="a@b.com", installed_apps=("frappe",)):
		session = {
			"site": "s1",
			"user": user,
			"user_type": "System User",
			"installed_apps": list(installed_apps),
			"_frappe_request": lambda path, args=None: {"message": 1},
		}
		self.sio.sessions["sid1"] = session
		return session

	def test_install_scoping_skips_uninstalled_app(self):
		calls = []
		with self.reg.importing_app("otherapp"):
			self.reg.on("evt")(lambda s: calls.append("ran"))
		self._session(installed_apps=("frappe",))
		dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, [])

	def test_install_scoping_runs_installed_app(self):
		calls = []
		with self.reg.importing_app("otherapp"):
			self.reg.on("evt")(lambda s: calls.append("ran"))
		self._session(installed_apps=("frappe", "otherapp"))
		dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, ["ran"])

	def test_guest_gate(self):
		calls = []
		self.reg.on("evt", allow_guest=False)(lambda s: calls.append("ran"))
		self._session(user="Guest")
		dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, [])

	def test_guest_allowed(self):
		calls = []
		self.reg.on("evt", allow_guest=True)(lambda s: calls.append("ran"))
		self._session(user="Guest")
		dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(calls, ["ran"])

	def test_frappe_context_wrap(self):
		entered = []

		@contextmanager
		def fake_ctx(site, user):
			entered.append((site, user))
			yield

		self.reg.on("evt", frappe_context=True)(lambda s: None)
		self._session()
		with patch.object(dispatch_mod, "frappe_context", fake_ctx):
			dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(entered, [("s1", "a@b.com")])

	def test_handler_error_swallowed(self):
		ran = []

		def boom(s):
			raise ValueError("boom")

		self.reg.on("evt")(boom)
		self.reg.on("evt")(lambda s: ran.append("after"))
		self._session()
		# Must not raise; the second handler still runs.
		dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ())
		self.assertEqual(ran, ["after"])

	def test_passes_event_args(self):
		seen = []
		self.reg.on("evt")(lambda s, a, b: seen.append((a, b)))
		self._session()
		dispatch_mod._run_handlers(self.sio, "evt", "/s1", "sid1", ("x", "y"))
		self.assertEqual(seen, [("x", "y")])


class TestBridge(unittest.TestCase):
	def setUp(self):
		self.sio = MagicMock()
		self.bridge = bridge_mod.RedisBridge(self.sio, "redis://x")

	def test_room_emit(self):
		self.bridge._handle('{"namespace": "s1", "room": "user:a", "event": "msg", "message": {"k": 1}}')
		self.sio.emit.assert_called_once_with("msg", {"k": 1}, room="user:a", namespace="/s1")

	def test_no_room_broadcast(self):
		self.sio.manager.rooms = {"/s1": {}, "/s2": {}}
		self.bridge._handle('{"namespace": "s1", "event": "build", "message": {"k": 1}}')
		self.assertEqual(self.sio.emit.call_count, 2)
		namespaces = {c.kwargs["namespace"] for c in self.sio.emit.call_args_list}
		self.assertEqual(namespaces, {"/s1", "/s2"})

	def test_malformed_message_skipped(self):
		self.bridge._handle("not json")
		self.bridge._handle('{"no_namespace": true}')
		self.sio.emit.assert_not_called()


class TestCoreHandlers(unittest.TestCase):
	def _socket(self, sio, frappe_request=None, **session):
		base = {"site": "s1", "user": "a@b.com", "user_type": "System User", "installed_apps": ["frappe"]}
		base.update(session)
		sio.sessions["sid1"] = base
		return Socket(sio, "sid1", "/s1", base, frappe_request)

	def test_ping_pong(self):
		sio = FakeSio()
		s = self._socket(sio)
		handlers_mod.ping(s)
		self.assertEqual(sio.emits[-1]["event"], "pong")

	def test_on_connect_joins_rooms(self):
		sio = FakeSio()
		s = self._socket(sio, user="a@b.com")
		handlers_mod.on_connect(s)
		rooms = sio.rooms_of("sid1")
		self.assertIn("user:a@b.com", rooms)
		self.assertIn("website", rooms)
		self.assertIn("all", rooms)  # System User

	def test_on_connect_website_user_skips_site_room(self):
		sio = FakeSio()
		s = self._socket(sio, user_type="Website User")
		handlers_mod.on_connect(s)
		self.assertNotIn("all", sio.rooms_of("sid1"))

	def test_doctype_subscribe_permission_gated(self):
		sio = FakeSio()
		allow = self._socket(sio, frappe_request=lambda p, a: {"message": 1})
		handlers_mod.doctype_subscribe(allow, "ToDo")
		self.assertIn("doctype:ToDo", sio.rooms_of("sid1"))

		sio2 = FakeSio()
		deny = self._socket(sio2, frappe_request=lambda p, a: {"message": 0})
		handlers_mod.doctype_subscribe(deny, "ToDo")
		self.assertNotIn("doctype:ToDo", sio2.rooms_of("sid1"))

	def test_doc_close_removes_tracked_pair(self):
		# Regression for the Node bug: the pair must actually be dropped.
		sio = FakeSio()
		s = self._socket(sio, subscribed_documents=[["ToDo", "n1"], ["ToDo", "n2"]])
		handlers_mod.doc_close(s, "ToDo", "n1")
		self.assertEqual(sio.sessions["sid1"]["subscribed_documents"], [["ToDo", "n2"]])

	def test_doc_viewers_emitted_for_multiple_users(self):
		sio = FakeSio()
		sio.sessions["sid1"] = {"user": "a@b.com"}
		sio.sessions["sid2"] = {"user": "b@b.com"}
		room = handlers_mod.open_doc_room("ToDo", "n1")
		sio.enter_room("sid1", room)
		sio.enter_room("sid2", room)
		s = Socket(sio, "sid1", "/s1", sio.sessions["sid1"])
		handlers_mod.notify_doc_viewers(s, "ToDo", "n1")
		emit = sio.emits[-1]
		self.assertEqual(emit["event"], "doc_viewers")
		self.assertEqual(set(emit["data"]["users"]), {"a@b.com", "b@b.com"})

	def test_doc_viewers_silent_for_lone_self(self):
		sio = FakeSio()
		sio.sessions["sid1"] = {"user": "a@b.com"}
		room = handlers_mod.open_doc_room("ToDo", "n1")
		sio.enter_room("sid1", room)
		s = Socket(sio, "sid1", "/s1", sio.sessions["sid1"])
		handlers_mod.notify_doc_viewers(s, "ToDo", "n1")
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
