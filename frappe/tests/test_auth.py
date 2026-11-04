# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import time

import requests

import frappe
from frappe.auth import LoginAttemptTracker, validate_auth
from frappe.core.doctype.user.user import generate_keys
from frappe.frappeclient import AuthError, FrappeClient
from frappe.sessions import Session, get_expired_sessions, get_expiry_in_seconds
from frappe.tests.test_api import FrappeAPITestCase
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime, get_site_url, now
from frappe.utils.data import add_to_date
from frappe.www.login import _generate_temporary_login_link


def add_user(email, password, username=None, mobile_no=None):
	first_name = email.split("@", 1)[0]
	user = frappe.get_doc(
		dict(doctype="User", email=email, first_name=first_name, username=username, mobile_no=mobile_no)
	).insert()
	user.new_password = password
	user.simultaneous_sessions = 1
	user.add_roles("System Manager")
	frappe.db.commit()


class TestAuth(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.HOST_NAME = frappe.get_site_config().host_name or get_site_url(frappe.local.site)
		cls.test_user_email = "test_auth@test.com"
		cls.test_user_name = "test_auth_user"
		cls.test_user_mobile = "+911234567890"
		cls.test_user_password = "pwd_012"

		cls.tearDownClass()
		add_user(
			email=cls.test_user_email,
			password=cls.test_user_password,
			username=cls.test_user_name,
			mobile_no=cls.test_user_mobile,
		)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.delete_doc("User", cls.test_user_email, force=True)
		frappe.local.request_ip = None
		frappe.form_dict.email = None
		frappe.local.response["http_status_code"] = None
		frappe.db.commit()

	def set_system_settings(self, k, v):
		frappe.db.set_single_value("System Settings", k, v)
		frappe.clear_cache()
		frappe.db.commit()

	def test_allow_login_using_mobile(self):
		self.set_system_settings("allow_login_using_mobile_number", 1)
		self.set_system_settings("allow_login_using_user_name", 0)

		# Login by both email and mobile should work
		FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)

		# login by username should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	def test_allow_login_using_only_email(self):
		self.set_system_settings("allow_login_using_mobile_number", 0)
		self.set_system_settings("allow_login_using_user_name", 0)

		# Login by mobile number should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)

		# login by username should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

		# Login by email should work
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)

	def test_allow_login_using_username(self):
		self.set_system_settings("allow_login_using_mobile_number", 0)
		self.set_system_settings("allow_login_using_user_name", 1)

		# Mobile login should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)

		# Both email and username logins should work
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	def test_allow_login_using_username_and_mobile(self):
		self.set_system_settings("allow_login_using_mobile_number", 1)
		self.set_system_settings("allow_login_using_user_name", 1)

		# Both email and username and mobile logins should work
		FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	def test_deny_multiple_login(self):
		self.set_system_settings("deny_multiple_sessions", 1)
		self.addCleanup(self.set_system_settings, "deny_multiple_sessions", 0)

		first_login = FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		first_login.get_list("ToDo")

		second_login = FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		second_login.get_list("ToDo")
		with self.assertRaises(Exception):
			first_login.get_list("ToDo")

		third_login = FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		with self.assertRaises(Exception):
			first_login.get_list("ToDo")
		with self.assertRaises(Exception):
			second_login.get_list("ToDo")
		third_login.get_list("ToDo")

	def test_disable_user_pass_login(self):
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password).get_list("ToDo")
		self.set_system_settings("disable_user_pass_login", 1)
		self.addCleanup(self.set_system_settings, "disable_user_pass_login", 0)

		with self.assertRaises(Exception):
			FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password).get_list("ToDo")

	def test_login_with_email_link(self):
		user = self.test_user_email

		# Logs in
		res = requests.get(_generate_temporary_login_link(user, 10))
		self.assertEqual(res.status_code, 200)
		self.assertTrue(res.cookies.get("sid"))
		self.assertNotEqual(res.cookies.get("sid"), "Guest")

		# Random incorrect URL
		res = requests.get(_generate_temporary_login_link(user, 10) + "aa")
		self.assertEqual(res.cookies.get("sid"), "Guest")

		# POST doesn't work
		res = requests.post(_generate_temporary_login_link(user, 10))
		self.assertEqual(res.status_code, 403)

		# Rate limiting
		for _ in range(6):
			res = requests.get(_generate_temporary_login_link(user, 10))
			if res.status_code == 429:
				break
		else:
			self.fail("Rate limting not working")

	def test_correct_cookie_expiry_set(self):
		import pytz

		client = FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)

		expiry_time = next(x for x in client.session.cookies if x.name == "sid").expires
		current_time = datetime.datetime.now(tz=pytz.UTC).timestamp()
		self.assertAlmostEqual(get_expiry_in_seconds(), expiry_time - current_time, delta=60 * 60)


class TestLoginAttemptTracker(FrappeTestCase):
	def test_account_lock(self):
		"""Make sure that account locks after `n consecutive failures"""
		tracker = LoginAttemptTracker("tester", max_consecutive_login_attempts=3, lock_interval=60)
		# Clear the cache by setting attempt as success
		tracker.add_success_attempt()

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertFalse(tracker.is_user_allowed())

	def test_account_unlock(self):
		"""Make sure that locked account gets unlocked after lock_interval of time."""
		lock_interval = 2  # In sec
		tracker = LoginAttemptTracker("tester", max_consecutive_login_attempts=1, lock_interval=lock_interval)
		# Clear the cache by setting attempt as success
		tracker.add_success_attempt()

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertFalse(tracker.is_user_allowed())

		# Sleep for lock_interval of time, so that next request con unlock the user access.
		time.sleep(lock_interval)

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())


class TestSessionExpiry(FrappeAPITestCase):
	def test_session_expires(self):
		sid = self.sid  # triggers login for test case login
		s: Session = frappe.local.session_obj

		expiry_in = get_expiry_in_seconds()
		session_created = now()

		# Try with 1% increments of times, it should always work
		for step in range(0, 100, 1):
			seconds_elapsed = expiry_in * step / 100

			time_now = add_to_date(session_created, seconds=seconds_elapsed, as_string=True)
			with self.freeze_time(time_now):
				data = s.get_session_data_from_db()
				self.assertEqual(data.user, "Administrator")

		# 1% higher should immediately expire
		time_of_expiry = add_to_date(session_created, seconds=expiry_in * 1.01, as_string=True)
		with self.freeze_time(time_of_expiry):
			self.assertIn(sid, get_expired_sessions())
			self.assertFalse(s.get_session_data_from_db())


class TestIPRestrictionForAPIAuth(FrappeTestCase):
	"""Header-authenticated requests must honour the user's `restrict_ip` allowlist.

	`validate_ip_address` runs in `LoginManager.post_login` for interactive logins and in
	`Session.resume` for cookie-based requests. A request authenticated purely from an
	`Authorization` header takes neither path, so `validate_auth` has to enforce it.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user_email = "test_api_ip_restriction@test.com"
		if not frappe.db.exists("User", cls.user_email):
			frappe.get_doc(doctype="User", email=cls.user_email, first_name="API IP Restricted").insert(
				ignore_permissions=True
			)

		cls.api_secret = generate_keys(cls.user_email)["api_secret"]
		cls.api_key = frappe.db.get_value("User", cls.user_email, "api_key")
		frappe.db.commit()

	def setUp(self):
		self._request = getattr(frappe.local, "request", None)
		self._request_ip = getattr(frappe.local, "request_ip", None)
		self._login_manager = getattr(frappe.local, "login_manager", None)
		self.addCleanup(self._restore)

	def _restore(self):
		frappe.local.request = self._request
		frappe.local.request_ip = self._request_ip
		frappe.local.login_manager = self._login_manager
		frappe.set_user("Administrator")

	def _authenticated_request_from(self, request_ip):
		"""Simulate an unauthenticated request carrying an API key/secret token."""
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		env = EnvironBuilder(
			headers={"Authorization": f"token {self.api_key}:{self.api_secret}"}
		).get_environ()
		frappe.local.request = Request(env)
		frappe.local.request_ip = request_ip
		frappe.local.login_manager = frappe._dict(user="Guest")
		frappe.set_user("Guest")

	def _set_restrict_ip(self, value):
		frappe.db.set_value("User", self.user_email, "restrict_ip", value)
		frappe.clear_cache(user=self.user_email)

	def test_api_auth_blocked_from_disallowed_ip(self):
		self._set_restrict_ip("192.168.255.254")
		self._authenticated_request_from("10.0.0.1")

		with self.assertRaises(frappe.AuthenticationError):
			validate_auth()

	def test_api_auth_allowed_from_allowed_ip(self):
		self._set_restrict_ip("10.0.0.1")
		self._authenticated_request_from("10.0.0.1")

		validate_auth()
		self.assertEqual(frappe.session.user, self.user_email)

	def test_api_auth_unaffected_without_ip_restriction(self):
		self._set_restrict_ip("")
		self._authenticated_request_from("10.0.0.1")

		validate_auth()
		self.assertEqual(frappe.session.user, self.user_email)
<<<<<<< HEAD
=======

	def test_auth_hook_user_without_user_record(self):
		frappe.local.request = Request(EnvironBuilder().get_environ())
		frappe.local.request_ip = "10.0.0.1"
		frappe.set_user("Guest")

		with patch(
			"frappe.auth.validate_auth_via_hooks",
			side_effect=lambda: frappe.set_user("no-such-user@example.com"),
		):
			validate_auth()

		self.assertEqual(frappe.session.user, "no-such-user@example.com")


class TestAPIKeyAuthFailureLog(IntegrationTestCase):
	"""Failed API key authentication is written to the Activity Log, a bounded number of times."""

	SUBJECT = "API key authentication failed%"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user_email = "test_api_auth_failure@example.com"
		if not frappe.db.exists("User", cls.user_email):
			frappe.get_doc(doctype="User", email=cls.user_email, first_name="API Auth Failure").insert(
				ignore_permissions=True
			)
		cls.api_secret = generate_keys(cls.user_email)["api_secret"]
		cls.api_key = frappe.db.get_value("User", cls.user_email, "api_key")

	def setUp(self):
		self._request = getattr(frappe.local, "request", None)
		self._request_ip = getattr(frappe.local, "request_ip", None)
		self._login_manager = getattr(frappe.local, "login_manager", None)
		self.addCleanup(self._restore)
		self._reset()

	def _restore(self):
		frappe.local.request = self._request
		frappe.local.request_ip = self._request_ip
		frappe.local.login_manager = self._login_manager
		frappe.set_user("Administrator")
		self._reset()

	def _reset(self):
		# Activity Log rows live in the log database, not in the site database
		db = get_log_db()
		qb, table = log_table("Activity Log")
		db.sql(qb.from_(table).where(table.subject.like(self.SUBJECT)).delete())
		db.commit()
		frappe.cache.delete_value(
			[f"api_auth_failure_logged:{self.user_email}", "api_auth_failure_logged:unknown"]
		)

	def _entries(self):
		return frappe.get_all(
			"Activity Log",
			filters={"subject": ["like", self.SUBJECT]},
			fields=["user", "status", "operation", "subject", "ip_address"],
		)

	def _request_with(self, api_key, api_secret, request_ip="10.0.0.1"):
		env = EnvironBuilder(headers={"Authorization": f"token {api_key}:{api_secret}"}).get_environ()
		frappe.local.request = Request(env)
		frappe.local.request_ip = request_ip
		frappe.local.login_manager = frappe._dict(user="Guest")
		frappe.set_user("Guest")

	def _fail_with(self, api_key, api_secret, **kwargs):
		self._request_with(api_key, api_secret, **kwargs)
		with self.assertRaises(frappe.AuthenticationError):
			validate_auth()

	def test_failed_api_key_auth_is_logged_without_the_credentials(self):
		self._fail_with(self.api_key, "not-the-secret")
		self._fail_with("unknown-key-123", "unknown-secret-456")

		entries = {entry.user: entry for entry in self._entries()}
		self.assertEqual(len(entries), 2)

		known = entries[self.user_email]
		self.assertEqual(known.status, "Failed")
		self.assertEqual(known.ip_address, "10.0.0.1")
		self.assertEqual(known.subject, "API key authentication failed: invalid API secret")

		unknown = next(entry for user, entry in entries.items() if user != self.user_email)
		self.assertEqual(unknown.subject, "API key authentication failed: invalid API key")
		for entry in entries.values():
			for sent in ("not-the-secret", "unknown-key-123", "unknown-secret-456", self.api_key):
				self.assertNotIn(sent, frappe.as_json(entry))

	def test_repeated_failures_are_logged_once_per_interval(self):
		for i in range(5):
			self._fail_with(self.api_key, "not-the-secret")
			self._fail_with(f"unknown-key-{i}", "x")

		self.assertEqual(len(self._entries()), 2)

	def test_failed_key_lookup_is_rejected_without_a_log_entry(self):
		self._request_with(self.api_key, "x")
		with self.assertRaises(frappe.AuthenticationError):
			validate_api_key_secret(self.api_key, "x", frappe_authorization_source="ToDo")

		self.assertEqual(self._entries(), [])


class TestLoginAttemptTracker(IntegrationTestCase):
	def test_account_lock(self):
		"""Make sure that account locks after `n consecutive failures"""
		tracker = LoginAttemptTracker("tester", max_consecutive_login_attempts=3, lock_interval=60)
		# Clear the cache by setting attempt as success
		tracker.add_success_attempt()

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertFalse(tracker.is_user_allowed())

	def test_account_unlock(self):
		"""Make sure that locked account gets unlocked after lock_interval of time."""
		lock_interval = 2  # In sec
		tracker = LoginAttemptTracker("tester", max_consecutive_login_attempts=1, lock_interval=lock_interval)
		# Clear the cache by setting attempt as success
		tracker.add_success_attempt()

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

		tracker.add_failure_attempt()
		self.assertFalse(tracker.is_user_allowed())

		# Sleep for lock_interval of time, so that next request con unlock the user access.
		time.sleep(lock_interval + 1)

		tracker.add_failure_attempt()
		self.assertTrue(tracker.is_user_allowed())

	def test_failure_counter_always_expires(self):
		tracker = LoginAttemptTracker("expiring-tester", max_consecutive_login_attempts=3, lock_interval=60)
		tracker.add_success_attempt()
		self.addCleanup(tracker.add_success_attempt)

		for _ in range(5):
			tracker.add_failure_attempt()
			self.assertGreater(frappe.cache.ttl(tracker.cache_key), 0)

	def test_tracker_ignores_an_unreachable_cache(self):
		tracker = LoginAttemptTracker("offline-tester", max_consecutive_login_attempts=1, lock_interval=60)
		down = redis.exceptions.ConnectionError

		with (
			patch.object(frappe.cache, "get", side_effect=down),
			patch.object(frappe.cache, "eval", side_effect=down),
			patch.object(frappe.cache, "delete", side_effect=down),
		):
			tracker.add_failure_attempt()
			tracker.add_failure_attempt()
			self.assertEqual(tracker.login_failed_count, 0)
			self.assertTrue(tracker.is_user_allowed())
			tracker.add_success_attempt()

	def test_concurrent_failures_are_all_counted(self):
		self.assert_concurrent_failures_are_counted(LoginAttemptTracker)

	def test_concurrent_failures_of_unknown_names_are_all_counted(self):
		self.assert_concurrent_failures_are_counted(UnknownUserLoginAttemptTracker)

	def assert_concurrent_failures_are_counted(self, tracker_class):
		site, sites_path = frappe.local.site, frappe.local.sites_path

		def new_tracker():
			return tracker_class("concurrent-tester", max_consecutive_login_attempts=10, lock_interval=60)

		tracker = new_tracker()
		tracker.add_success_attempt()
		self.addCleanup(tracker.add_success_attempt)

		attempts = 20
		barrier = threading.Barrier(attempts, timeout=10)

		def fail_login(_):
			try:
				frappe.init(site, sites_path=sites_path)
				frappe.connect()
				barrier.wait()
				new_tracker().add_failure_attempt()
			finally:
				frappe.destroy()

		with ThreadPoolExecutor(max_workers=attempts) as pool:
			list(pool.map(fail_login, range(attempts)))

		self.assertEqual(tracker.login_failed_count, attempts)
		self.assertFalse(tracker.is_user_allowed())


class TestSessionIdHashing(FrappeAPITestCase):
	"""Sessions are stored under the sha256 of the sid, never the sid itself.

	The raw sid lives only in the client's cookie, so a dump of `tabSessions` or of the
	session cache yields nothing that can be replayed as a session.
	"""

	def sessions_row(self, stored_sid):
		sessions = frappe.qb.DocType("Sessions")
		return frappe.qb.from_(sessions).select(sessions.user).where(sessions.sid == stored_sid).run()

	def test_raw_sid_is_never_stored(self):
		sid = self.sid
		self.assertFalse(self.sessions_row(sid), "raw sid must not appear in tabSessions")
		self.assertFalse(frappe.cache.hget("session", sid), "raw sid must not key the session cache")

	def test_session_is_stored_under_its_hash(self):
		sid = self.sid
		row = self.sessions_row(hash_sid(sid))
		self.assertTrue(row, "session must be stored under the hash of the sid")
		self.assertEqual(row[0][0], "Administrator")
		self.assertTrue(frappe.cache.hget("session", hash_sid(sid)))

	def test_cached_payload_does_not_carry_the_sid(self):
		sid = self.sid
		payload = frappe.cache.hget("session", hash_sid(sid))
		self.assertNotIn("sid", payload, "the cached session must not carry the raw sid")

	def request_with_cookie(self, sid):
		"""Put a request carrying `sid` on this thread, restored when the test ends."""
		from frappe.utils import set_request

		original_request = getattr(frappe.local, "request", None)
		if original_request is not None:
			self.addCleanup(setattr, frappe.local, "request", original_request)
		else:
			self.addCleanup(delattr, frappe.local, "request")

		set_request(path="/")
		frappe.local.request.cookies = {"sid": sid}

	def test_raw_cookie_resumes_the_session(self):
		self.request_with_cookie(self.sid)
		self.assertEqual(Session(user=None, resume=True).user, "Administrator")

	def test_sid_hash_follows_sid(self):
		self.request_with_cookie(self.sid)
		session = Session(user=None, resume=True)
		session.sid = "a" * 32
		self.assertEqual(session.sid_hash, sha256_hash("a" * 32))

	def test_guest_sid_is_not_hashed(self):
		self.assertEqual(hash_sid("Guest"), "Guest")


class TestSessionExpiry(FrappeAPITestCase):
	def test_session_expires(self):
		sid = self.sid  # triggers login for test case login
		s: Session = frappe.local.session_obj

		expiry_in = get_expiry_in_seconds()
		session_created = now()

		# Try with 1% increments of times, it should always work
		for step in range(0, 100, 1):
			seconds_elapsed = expiry_in * step / 100

			time_now = add_to_date(session_created, seconds=seconds_elapsed, as_string=True)
			with self.freeze_time(time_now):
				data = s.get_session_data_from_db()
				self.assertEqual(data.user, "Administrator")

		# 1% higher should immediately expire
		time_of_expiry = add_to_date(session_created, seconds=expiry_in * 1.01, as_string=True)
		with self.freeze_time(time_of_expiry):
			# sessions are stored under the hash of the sid, not the raw cookie value
			self.assertIn(hash_sid(sid), get_expired_sessions())
			self.assertFalse(s.get_session_data_from_db())

	def test_expired_session_answers_401_without_leaking_method(self):
		from frappe.auth import get_logged_user

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.local.response.pop, "session_expired", None)
		self.addCleanup(frappe.clear_messages)

		frappe.local.response["session_expired"] = 1
		frappe.clear_messages()
		with self.assertRaises(frappe.SessionExpired):
			frappe.is_whitelisted(get_logged_user)
		self.assertEqual(
			frappe.get_message_log(), [], "an expired session must not send a message to the client"
		)

		frappe.local.response.pop("session_expired", None)
		with self.assertRaises(frappe.PermissionError):
			frappe.is_whitelisted(get_logged_user)

		def not_whitelisted():
			pass

		frappe.local.response["session_expired"] = 1
		with self.assertRaises(frappe.PermissionError):
			frappe.is_whitelisted(not_whitelisted)
>>>>>>> d8136b9 (fix: allow auth hooks to set a user without a User record)
