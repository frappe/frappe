import datetime
from unittest.mock import patch

import pyotp

import frappe
from frappe.auth import get_login_attempt_tracker
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import make_request
from frappe.twofactor import clear_default, get_otpsecret_for_, set_default
from frappe.utils import get_test_client


class TestTwoFactorLogin(IntegrationTestCase):
	"""HTTP requests use separate database connections, so fixtures and cleanup require commits."""

	user = "twofactor-login@example.com"
	password = "TwoFactor-login-43A1W"
	role = "_Test Two Factor Login"

	def setUp(self):
		super().setUp()
		self.enterContext(patch("frappe.sendmail", return_value=True))
		self.enterContext(self.freeze_time(datetime.datetime.now()))
		self.enterContext(
			self.change_settings(
				"System Settings",
				{
					"enable_two_factor_auth": 1,
					"two_factor_method": "OTP App",
					"allow_consecutive_login_attempts": 2,
					"allow_login_after_fail": 300,
				},
				commit=True,
			)
		)
		self.client = get_test_client(use_cookies=False)
		self.tmp_ids = []
		self.addCleanup(self.cleanup_login)
		frappe.get_doc(doctype="Role", role_name=self.role, two_factor_auth=1).insert()
		frappe.get_doc(
			doctype="User",
			email=self.user,
			first_name="Two Factor Login",
			new_password=self.password,
			send_welcome_email=0,
			roles=[{"role": self.role}],
		).insert()
		self.secret = get_otpsecret_for_(self.user)
		frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit

	def test_otp_app_enrollment(self):
		tmp_id = self.start_login()
		response = self.post_login({"tmp_id": tmp_id, "otp": self.email_code(tmp_id)})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["verification"]["otp_secret"], self.secret)
		self.assertNotIn("message", response.json)
		response = self.post_login({"tmp_id": tmp_id, "otp": pyotp.TOTP(self.secret).now()})
		self.assert_logged_in(response)

	def test_enrolled_otp_app_login(self):
		set_default(self.user + "_otplogin", 1)
		frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
		tmp_id = self.start_login(method="OTP App")
		response = self.post_login({"tmp_id": tmp_id, "otp": pyotp.TOTP(self.secret).now()})
		self.assert_logged_in(response)

	def test_email_login(self):
		with self.change_settings("System Settings", {"two_factor_method": "Email"}, commit=True):
			tmp_id = self.start_login()
			response = self.post_login({"tmp_id": tmp_id, "otp": self.email_code(tmp_id)})
			self.assert_logged_in(response)

	def test_email_login_with_zero_token(self):
		with self.change_settings("System Settings", {"two_factor_method": "Email"}, commit=True):
			with patch("pyotp.TOTP.now", return_value="000000"):
				tmp_id = self.start_login()
			self.assertEqual(frappe.cache.get_value(tmp_id + "_token", expires=True), 0)
			response = self.post_login({"tmp_id": tmp_id, "otp": self.email_code(tmp_id)})
			self.assert_logged_in(response)
			self.assertIsNone(frappe.cache.get_value(tmp_id + "_token", expires=True))

	def test_incomplete_login_preserves_pending_logins(self):
		tmp_id = self.start_login()
		code = self.email_code(tmp_id)
		response = self.post_login({})
		self.assertEqual(response.status_code, 401)
		response = self.post_login({"tmp_id": tmp_id, "otp": code})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["verification"]["otp_secret"], self.secret)

	def test_otp_attempt_limit_survives_login_restarts(self):
		tmp_id = self.start_login()
		code = self.email_code(tmp_id)
		for credentials in (
			{"usr": self.user, "pwd": self.password},
			{"usr": self.user, "tmp_id": tmp_id},
			{"tmp_id": tmp_id},
		):
			response = self.post_login(credentials)
			self.assertEqual(response.status_code, 200)
			response = self.post_login({"tmp_id": tmp_id, "otp": "wrong-code"})
			self.assertEqual(response.status_code, 401)

		response = self.post_login({"tmp_id": tmp_id, "otp": code})
		self.assertEqual(response.json.get("exc_type"), "SecurityException")
		response = self.post_login({"usr": self.user, "pwd": self.password})
		self.assertEqual(response.json.get("exc_type"), "SecurityException")

	def test_otp_success_resets_attempt_limit(self):
		tmp_id = self.start_login()
		response = self.post_login({"tmp_id": tmp_id, "otp": "wrong-code"})
		self.assertEqual(response.status_code, 401)
		response = self.post_login({"tmp_id": tmp_id, "otp": self.email_code(tmp_id)})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["verification"]["otp_secret"], self.secret)
		tracker = get_login_attempt_tracker(self.user)
		self.assertEqual(tracker.login_failed_count, 1)
		response = self.post_login({"tmp_id": tmp_id, "otp": pyotp.TOTP(self.secret).now()})
		self.assert_logged_in(response)
		self.assertFalse(tracker.login_failed_count)

	def test_password_login_resets_attempt_limit_without_2fa(self):
		with self.change_settings("System Settings", {"enable_two_factor_auth": 0}, commit=True):
			response = self.post_login({"usr": self.user, "pwd": "wrong-password"})
			self.assertEqual(response.status_code, 401)
			tracker = get_login_attempt_tracker(self.user)
			self.assertEqual(tracker.login_failed_count, 1)
			response = self.post_login({"usr": self.user, "pwd": self.password})
			self.assert_logged_in(response)
			self.assertFalse(tracker.login_failed_count)

	def start_login(self, method="Email"):
		response = self.post_login({"usr": self.user, "pwd": self.password})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["verification"]["method"], method)
		self.assertNotIn("otp_secret", response.json["verification"])
		return response.json["tmp_id"]

	def post_login(self, data):
		response = make_request(
			target=self.client.post,
			args=("/api/method/login",),
			kwargs={"data": data},
			site=frappe.local.site,
		)
		frappe.db.rollback()
		frappe.local.cache = {}
		if tmp_id := response.json.get("tmp_id"):
			self.tmp_ids.append(tmp_id)
		return response

	def email_code(self, tmp_id):
		token = frappe.cache.get_value(tmp_id + "_token", use_local_cache=False)
		return pyotp.HOTP(self.secret).at(token)

	def assert_logged_in(self, response):
		self.assertEqual(response.status_code, 200)
		self.assertIn(response.json.get("message"), ("Logged In", "No App"))
		self.assertTrue(any(cookie.startswith("sid=") for cookie in response.headers.getlist("Set-Cookie")))

	def cleanup_login(self):
		frappe.db.rollback()
		for suffix in ("_otpsecret", "_otplogin"):
			clear_default(self.user + suffix)
		get_login_attempt_tracker(self.user, raise_locked_exception=False).add_success_attempt()
		for tmp_id in self.tmp_ids:
			frappe.cache.delete_value(
				[tmp_id + suffix for suffix in ("_usr", "_pwd", "_otp_secret", "_token", "_email_verified")]
			)
		for doctype, name in (("User", self.user), ("Role", self.role)):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=True)
		frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
