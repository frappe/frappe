# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.core.doctype.user.user import expire_user_statuses
from frappe.core.doctype.user.user import set_status as set_status_whitelisted
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime


class TestUserStatus(IntegrationTestCase):
	TEST_USER = "test@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.user = frappe.get_doc("User", self.TEST_USER)
		# clear state before each test
		self.user.set_status(None)

	def tearDown(self):
		frappe.set_user("Administrator")
		try:
			frappe.get_doc("User", self.TEST_USER).set_status(None)
		except Exception:
			pass

	def _reload_status_fields(self):
		row = frappe.db.get_value(
			"User",
			self.TEST_USER,
			["user_status", "user_status_expires_at"],
			as_dict=True,
		)
		return row.user_status, row.user_status_expires_at

	def test_set_status_persists(self):
		result = self.user.set_status("Available")
		self.assertEqual(result["status"], "Available")
		self.assertIsNone(result["expires_at"])

		status, expires_at = self._reload_status_fields()
		self.assertEqual(status, "Available")
		self.assertIsNone(expires_at)

	def test_set_status_with_expiry(self):
		future = add_to_date(now_datetime(), hours=1)
		self.user.set_status("Out of Office", expires_at=future)
		status, expires_at = self._reload_status_fields()
		self.assertEqual(status, "Out of Office")
		self.assertIsNotNone(expires_at)

	def test_clear_status(self):
		self.user.set_status("Busy")
		self.user.set_status(None)
		status, expires_at = self._reload_status_fields()
		self.assertIsNone(status)
		self.assertIsNone(expires_at)

	def test_set_status_invalidates_cache(self):
		# prime cache
		self.user.set_status("Available")
		cached_before = self.user.get_status()
		self.assertEqual(cached_before["status"], "Available")

		# write directly to db to verify cache is the data path
		frappe.db.set_value("User", self.TEST_USER, "user_status", "Busy", update_modified=False)
		# cache is still warm, returns old value
		self.assertEqual(self.user.get_status()["status"], "Available")

		# set_status should invalidate cache
		self.user.set_status("Do Not Disturb")
		self.assertEqual(self.user.get_status()["status"], "Do Not Disturb")

	def test_set_status_does_not_bump_modified(self):
		original_modified = frappe.db.get_value("User", self.TEST_USER, "modified")
		self.user.set_status("Available")
		new_modified = frappe.db.get_value("User", self.TEST_USER, "modified")
		self.assertEqual(original_modified, new_modified)

	def test_user_status_change_hook_fires_with_string_args(self):
		captured = []

		def fake_handler(user, old, new):
			captured.append({"user": user, "old": old, "new": new})

		original_get_hooks = frappe.get_hooks

		def fake_get_hooks(*args, **kwargs):
			hook_name = args[0] if args else kwargs.get("hook")
			if hook_name == "user_status_change":
				return [fake_handler]
			return original_get_hooks(*args, **kwargs)

		with patch.object(frappe, "get_hooks", side_effect=fake_get_hooks):
			self.user.set_status("Away")
			self.user.set_status("Busy")

		self.assertEqual(len(captured), 2)
		# first transition: None -> Away
		self.assertEqual(captured[0]["user"], self.TEST_USER)
		self.assertIsNone(captured[0]["old"])
		self.assertEqual(captured[0]["new"], "Away")
		# second transition: Away -> Busy
		self.assertEqual(captured[1]["old"], "Away")
		self.assertEqual(captured[1]["new"], "Busy")
		# old/new are strings (or None), not dicts
		for ev in captured:
			self.assertNotIsInstance(ev["old"], dict)
			self.assertNotIsInstance(ev["new"], dict)

	def test_scheduler_clears_expired_statuses(self):
		past = now_datetime() - timedelta(minutes=5)
		self.user.set_status("Out of Office", expires_at=past)
		expire_user_statuses()
		status, expires_at = self._reload_status_fields()
		self.assertIsNone(status)
		self.assertIsNone(expires_at)

	def test_scheduler_leaves_future_statuses_alone(self):
		future = now_datetime() + timedelta(hours=1)
		self.user.set_status("Out of Office", expires_at=future)
		expire_user_statuses()
		status, _ = self._reload_status_fields()
		self.assertEqual(status, "Out of Office")

	def test_whitelisted_set_status_targets_session_user(self):
		try:
			frappe.set_user(self.TEST_USER)
			set_status_whitelisted("Available")
			status, _ = self._reload_status_fields()
			self.assertEqual(status, "Available")
		finally:
			frappe.set_user("Administrator")

	def test_whitelisted_set_status_rejects_guest(self):
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				set_status_whitelisted("Available")
		finally:
			frappe.set_user("Administrator")

	def test_instance_set_status_is_not_whitelisted(self):
		# `User.set_status` must remain a developer-only API. The dispatch
		# layer rejects non-whitelisted instance methods.
		from frappe.handler import run_doc_method

		with self.assertRaises(frappe.PermissionError):
			run_doc_method(
				method="set_status",
				dt="User",
				dn=self.TEST_USER,
				args={"status": "Available"},
			)

	def test_add_user_info_includes_status_fields(self):
		from frappe.utils import add_user_info

		future = add_to_date(now_datetime(), hours=1)
		self.user.set_status("Available", expires_at=future)

		info = {}
		add_user_info(self.TEST_USER, info)
		row = info[self.TEST_USER]
		self.assertEqual(row.get("user_status"), "Available")
		self.assertIsNotNone(row.get("user_status_expires_at"))
