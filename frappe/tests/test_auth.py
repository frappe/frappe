# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import redis
import requests
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

import frappe
from frappe.auth import (
	CookieManager,
	LoginAttemptTracker,
	LoginManager,
	UnknownUserLoginAttemptTracker,
	get_login_attempt_tracker,
	validate_api_key_secret,
	validate_auth,
	validate_ip_address,
)
from frappe.core.doctype.user.user import User, generate_keys
from frappe.frappeclient import AuthError, FrappeClient
from frappe.sessions import Session, get_expired_sessions, get_expiry_in_seconds, hash_sid
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.tests.test_api import FrappeAPITestCase
from frappe.tests.utils.test_capabilities import TestService, requires_test_service
from frappe.utils import get_datetime, get_site_url, now
from frappe.utils.data import add_to_date, sha256_hash
from frappe.utils.logging import get_log_db, log_table
from frappe.utils.password import check_password
from frappe.www.login import _generate_temporary_login_link


def add_user(email, password, username=None, mobile_no=None):
	first_name = email.split("@", 1)[0]
	user = frappe.get_doc(
		doctype="User", email=email, first_name=first_name, username=username, mobile_no=mobile_no
	).insert()
	user.new_password = password
	user.simultaneous_sessions = 1
	user.add_roles("System Manager")
	frappe.db.commit()


class TestAuth(IntegrationTestCase):
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

	def test_validate_ip_address_without_a_request(self):
		with (
			patch.object(frappe.local, "request", None, create=True),
			patch(
				"frappe.auth.frappe.get_cached_doc",
				return_value=Mock(get_restricted_ip_list=lambda: []),
			),
		):
			self.assertIsNone(validate_ip_address("Administrator"))

	def test_session_without_a_request_uses_guest_sid(self):
		original_session = frappe.local.session
		self.addCleanup(setattr, frappe.local, "session", original_session)

		with patch.object(frappe.local, "request", None, create=True):
			self.assertEqual(Session(user="").sid, "Guest")

	def test_cookie_manager_without_a_request_uses_non_secure_cookie(self):
		with patch.object(frappe.local, "request", None, create=True):
			cookies = CookieManager()
			cookies.set_cookie("sid", "test")
			self.assertFalse(cookies.cookies["sid"]["secure"])

	def test_locked_account_response_matches_unknown_account(self):
		self.addCleanup(frappe.form_dict.clear)
		unknown = "unknown_auth@example.com"
		ips = [f"10.8.0.{i}" for i in range(6)]

		def cleanup():
			for key in [self.test_user_email, *ips]:
				LoginAttemptTracker(key).add_success_attempt()
			get_login_attempt_tracker(
				unknown, raise_locked_exception=False, unknown_user=True
			).add_success_attempt()

		self.addCleanup(cleanup)

		def attempt(usr, ip):
			frappe.local.request_ip = ip
			frappe.local.response = frappe._dict()
			frappe.local.message_log = []
			frappe.form_dict.update({"usr": usr, "pwd": "wrong_pwd_012"})
			try:
				LoginManager.__new__(LoginManager).authenticate()
			except (frappe.AuthenticationError, frappe.SecurityException) as e:
				return (
					type(e),
					frappe.local.response.get("message"),
					[m["message"] for m in frappe.local.message_log],
				)

		with self.change_settings("System Settings", commit=True, allow_consecutive_login_attempts=2):
			known = [attempt(self.test_user_email, ip) for ip in ips]
			unknown_results = [attempt(unknown, ip) for ip in ips]

		self.assertEqual(known, unknown_results)
		self.assertEqual(known[0][:2], (frappe.AuthenticationError, "Invalid login credentials"))
		self.assertEqual(known[-1][0], frappe.SecurityException)
		self.assertIn("Too many failed login attempts", known[-1][2][0])

	def test_unknown_account_login_without_lock_interval(self):
		self.addCleanup(frappe.form_dict.clear)
		settings = {"allow_consecutive_login_attempts": 2, "allow_login_after_fail": 0}
		with self.change_settings("System Settings", commit=True, **settings):
			frappe.local.request_ip = "10.8.1.1"
			frappe.local.response = frappe._dict()
			frappe.form_dict.update({"usr": "unknown_auth@example.com", "pwd": "wrong_pwd_012"})
			with self.assertRaises(frappe.AuthenticationError):
				LoginManager.__new__(LoginManager).authenticate()
		self.assertEqual(frappe.local.response.get("message"), "Invalid login credentials")

	def test_unknown_account_checks_a_password_hash(self):
		with patch("frappe.utils.password.verify_password", return_value=(False, False)) as verify:
			self.assertIsNone(User.find_by_credentials("unknown_auth@example.com", "wrong_pwd_012"))
		verify.assert_called_once()

	def test_user_without_a_password_checks_a_password_hash(self):
		email = "no_password_auth@example.com"
		frappe.delete_doc("User", email, force=True)
		frappe.get_doc(doctype="User", email=email, first_name="No Password", send_welcome_email=0).insert()
		self.addCleanup(frappe.delete_doc, "User", email, force=True)

		with patch("frappe.utils.password.verify_password", return_value=(False, False)) as verify:
			with self.assertRaises(frappe.AuthenticationError):
				check_password(email, "wrong_pwd_012")
		verify.assert_called_once()

	@requires_test_service(TestService.WEB_SERVER)
	def test_allow_login_using_mobile(self):
		self.set_system_settings("allow_login_using_mobile_number", 1)
		self.set_system_settings("allow_login_using_user_name", 0)

		# Login by both email and mobile should work
		FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)

		# login by username should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	@requires_test_service(TestService.WEB_SERVER)
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

	@requires_test_service(TestService.WEB_SERVER)
	def test_allow_login_using_username(self):
		self.set_system_settings("allow_login_using_mobile_number", 0)
		self.set_system_settings("allow_login_using_user_name", 1)

		# Mobile login should fail
		with self.assertRaises(AuthError):
			FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)

		# Both email and username logins should work
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	@requires_test_service(TestService.WEB_SERVER)
	def test_allow_login_using_username_and_mobile(self):
		self.set_system_settings("allow_login_using_mobile_number", 1)
		self.set_system_settings("allow_login_using_user_name", 1)

		# Both email and username and mobile logins should work
		FrappeClient(self.HOST_NAME, self.test_user_mobile, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)
		FrappeClient(self.HOST_NAME, self.test_user_name, self.test_user_password)

	@requires_test_service(TestService.WEB_SERVER)
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

	@requires_test_service(TestService.WEB_SERVER)
	def test_disable_user_pass_login(self):
		FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password).get_list("ToDo")
		self.set_system_settings("disable_user_pass_login", 1)
		self.addCleanup(self.set_system_settings, "disable_user_pass_login", 0)

		with self.assertRaises(Exception):
			FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password).get_list("ToDo")

	def test_forced_password_reset_does_not_leak_reset_key(self):
		from frappe.auth import LoginManager
		from frappe.utils import add_days, set_request, today

		self.set_system_settings("force_user_to_reset_password", 1)
		self.addCleanup(self.set_system_settings, "force_user_to_reset_password", 0)

		frappe.db.set_value("User", self.test_user_email, "last_password_reset_date", add_days(today(), -2))
		frappe.db.commit()

		set_request(method="POST", path="/api/method/login")
		frappe.form_dict.usr = self.test_user_email
		frappe.form_dict.pwd = self.test_user_password
		frappe.local.response = frappe._dict()
		frappe.local.request_ip = "127.0.0.68"
		self.addCleanup(frappe.form_dict.clear)

		emails_before = frappe.db.count("Email Queue")

		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()

		self.assertEqual(frappe.local.response.get("message"), "Password Reset")
		self.assertNotIn("redirect_to", frappe.local.response)
		self.assertGreater(frappe.db.count("Email Queue"), emails_before)

	def test_forced_password_reset_waits_for_2fa(self):
		from frappe.auth import LoginManager
		from frappe.utils import add_days, set_request, today

		system_settings = frappe.get_doc("System Settings")
		system_settings.enable_two_factor_auth = 1
		system_settings.two_factor_method = "OTP App"
		system_settings.flags.ignore_mandatory = True
		system_settings.save(ignore_permissions=True)
		self.addCleanup(self.set_system_settings, "enable_two_factor_auth", 0)

		self.set_system_settings("force_user_to_reset_password", 1)
		self.addCleanup(self.set_system_settings, "force_user_to_reset_password", 0)

		frappe.db.set_value("User", self.test_user_email, "last_password_reset_date", add_days(today(), -2))
		frappe.db.commit()

		set_request(method="POST", path="/api/method/login")
		frappe.form_dict.usr = self.test_user_email
		frappe.form_dict.pwd = self.test_user_password
		frappe.local.response = frappe._dict()
		frappe.local.request_ip = "127.0.0.69"
		self.addCleanup(frappe.form_dict.clear)

		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()

		self.assertIn("tmp_id", frappe.local.response)
		self.assertNotEqual(frappe.local.response.get("message"), "Password Reset")
		self.assertNotIn("redirect_to", frappe.local.response)

	def test_forced_password_reset_counts_from_account_creation(self):
		from frappe.auth import LoginManager
		from frappe.utils import add_days, set_request, today

		self.set_system_settings("force_user_to_reset_password", 1)
		self.addCleanup(self.set_system_settings, "force_user_to_reset_password", 0)

		frappe.db.set_value(
			"User",
			self.test_user_email,
			{"last_password_reset_date": None, "creation": add_days(today(), -2)},
		)

		set_request(method="POST", path="/api/method/login")
		frappe.form_dict.usr = self.test_user_email
		frappe.form_dict.pwd = self.test_user_password
		frappe.local.response = frappe._dict()
		frappe.local.request_ip = "127.0.0.70"
		self.addCleanup(frappe.form_dict.clear)

		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()

		self.assertEqual(frappe.local.response.get("message"), "Password Reset")

	@requires_test_service(TestService.WEB_SERVER)
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

	@requires_test_service(TestService.WEB_SERVER)
	def test_correct_cookie_expiry_set(self):
		client = FrappeClient(self.HOST_NAME, self.test_user_email, self.test_user_password)

		expiry_time = next(x for x in client.session.cookies if x.name == "sid").expires
		current_time = datetime.datetime.now(tz=datetime.UTC).timestamp()
		self.assertAlmostEqual(get_expiry_in_seconds(), expiry_time - current_time, delta=60 * 60)


class TestAllowedReferrer(UnitTestCase):
	def test_is_allowed_referrer(self):
		def create_request(headers):
			builder = EnvironBuilder(headers=headers)
			env = builder.get_environ()
			return Request(env)

		# Set a single allowed referrer
		frappe.cache.set_value("allowed_referrers", ["https://example.com"])

		# Test with valid referrer
		frappe.local.request = create_request({"Referer": "https://example.com/some/path"})
		http_request = frappe.auth.HTTPRequest()
		self.assertTrue(http_request.is_allowed_referrer())

		# Test with invalid referrer
		frappe.local.request = create_request({"Referer": "https://malicious.com"})
		http_request = frappe.auth.HTTPRequest()
		self.assertFalse(http_request.is_allowed_referrer())

		# Test with valid origin
		frappe.local.request = create_request({"Origin": "https://example.com"})
		http_request = frappe.auth.HTTPRequest()
		self.assertTrue(http_request.is_allowed_referrer())

		# Test with invalid origin
		frappe.local.request = create_request({"Origin": "https://malicious.com"})
		http_request = frappe.auth.HTTPRequest()
		self.assertFalse(http_request.is_allowed_referrer())

		# Test subdomain bypass prevention
		frappe.local.request = create_request({"Referer": "https://example.com.evil.com"})
		http_request = frappe.auth.HTTPRequest()
		self.assertFalse(http_request.is_allowed_referrer())

		# Test exact domain match for referrer
		frappe.local.request = create_request({"Referer": "https://example.com"})
		http_request = frappe.auth.HTTPRequest()
		self.assertTrue(http_request.is_allowed_referrer())

		# Clean up
		frappe.cache.delete_value("allowed_referrers")
		frappe.local.request = None


class TestIPRestrictionForAPIAuth(IntegrationTestCase):
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
		time.sleep(lock_interval)

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
