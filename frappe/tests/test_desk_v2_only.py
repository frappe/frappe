# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import importlib
import pkgutil

import frappe
import frappe.shell
from frappe.core.doctype.user.user import generate_keys
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import FrappeAPITestCase

DESK_USER = "desk-v2-only-user@example.com"
SHELL_ONLY = "frappe.email.inbox.get_outgoing_senders"
FRAMEWORK_UI = "frappe.onboarding.update_onboarding_status"
SHELL_ONLY_LATER = (
	"frappe.desk.ui_relay.tabs",
	"frappe.desk.ui_relay.call",
	"frappe.desk.ui_relay.reply",
	"frappe.core.doctype.deleted_document.deleted_document.restore_record",
	"frappe.email.doctype.email_queue.email_queue.retry_record",
	"frappe.email.inbox.mark_read_unread",
	"frappe.core.doctype.user.user.add_roles_to_user",
	"frappe.core.doctype.user.user.remove_roles_from_user",
	"frappe.desk.doctype.tag.tag.set_tag_color",
	"frappe.desk.doctype.tag.tag.update_record_tags",
	"frappe.core.doctype.doctype.doctype.write_doctype_files",
	"frappe.model.document.Document.queue_submit",
	"frappe.model.document.Document.queue_cancel",
)
# Called by `@framework/ui` in other apps: they stay open with the switch off.
FRAMEWORK_UI_OPEN = (
	"frappe.onboarding.update_onboarding_status",
	"frappe.core.api.user_invitation.get_invited_emails",
)


class TestDeskV2OnlyMethods(FrappeAPITestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("User", DESK_USER):
			frappe.get_doc(doctype="User", email=DESK_USER, first_name="Desk", send_welcome_email=0).insert(
				ignore_permissions=True
			)
		frappe.get_doc("User", DESK_USER).add_roles("Desk User")
		api_secret = generate_keys(DESK_USER)["api_secret"]
		api_key = frappe.db.get_value("User", DESK_USER, "api_key")
		cls.auth = {"Authorization": f"token {api_key}:{api_secret}"}
		# The test client serves each request on its own connection, which must see the keys.
		frappe.db.commit()  # nosemgrep

	def call(self, method: str):
		if method == FRAMEWORK_UI:
			return self.post(self.method(method), {"steps": "[]", "app": "frappe"}, headers=self.auth)
		return self.get(self.method(method), headers=self.auth)

	def test_switch_off_refuses_shell_only_methods(self):
		with self.change_settings("System Settings", commit=True, enable_desk_v2=0):
			response = self.call(SHELL_ONLY)
			self.assertEqual(response.status_code, 403)
			self.assertEqual(response.json["exc_type"], "DeskV2DisabledError")
			self.assertEqual(self.call(FRAMEWORK_UI).status_code, 200)

	def test_switch_on_answers_both(self):
		with self.change_settings("System Settings", commit=True, enable_desk_v2=1):
			self.assertEqual(self.call(SHELL_ONLY).status_code, 200)
			self.assertEqual(self.call(FRAMEWORK_UI).status_code, 200)


class TestDeskV2OnlyDecorator(IntegrationTestCase):
	def test_must_sit_above_whitelist(self):
		def method():
			pass

		self.assertRaises(TypeError, frappe.desk_v2_only, method)

	def test_every_shell_method_is_gated(self):
		for module in pkgutil.walk_packages(frappe.shell.__path__, "frappe.shell."):
			importlib.import_module(module.name)

		open_shell_methods = [
			f"{fn.__module__}.{fn.__qualname__}"
			for fn in frappe.whitelisted
			if fn.__module__.startswith("frappe.shell.") and fn not in frappe.desk_v2_methods
		]
		self.assertEqual(open_shell_methods, [])

	def test_switch_off_refuses_later_shell_methods(self):
		with self.change_settings("System Settings", enable_desk_v2=0):
			for path in SHELL_ONLY_LATER:
				with self.subTest(path):
					fn = _resolve(path)
					self.assertIn(fn, frappe.desk_v2_methods)
					self.assertRaises(frappe.DeskV2DisabledError, frappe.is_whitelisted, fn)

	def test_switch_off_keeps_framework_ui_methods_open(self):
		with self.change_settings("System Settings", enable_desk_v2=0):
			for path in FRAMEWORK_UI_OPEN:
				with self.subTest(path):
					fn = _resolve(path)
					self.assertNotIn(fn, frappe.desk_v2_methods)
					frappe.is_whitelisted(fn)


def _resolve(path: str):
	"""The function behind a dotted path to a module function or a class method."""
	parts = path.split(".")
	for n in range(len(parts) - 1, 0, -1):
		try:
			obj = importlib.import_module(".".join(parts[:n]))
		except ImportError:
			continue
		for part in parts[n:]:
			obj = getattr(obj, part)
		return obj
	raise ImportError(path)
