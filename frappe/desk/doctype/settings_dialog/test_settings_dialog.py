# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import contextlib
import json
from unittest.mock import patch

import frappe
from frappe.desk.doctype.settings_dialog.settings_dialog import SettingsDialog
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

# Never installed: `app` and `extends` are `Autocomplete`, not Links.
HOST = "acme"
EXTENDER = "telephony"

AUTHOR = "settings-author@example.com"


@contextlib.contextmanager
def authoring(user: str = AUTHOR, developer: bool = True):
	"""Author as this user, with the export patched so no file lands in the working tree."""
	original = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 1 if developer else 0
	try:
		with set_user(user), patch.object(SettingsDialog, "export_settings_dialog"):
			yield
	finally:
		frappe.conf.developer_mode = original


def ship(panes=(), blocks=(), *, app: str = HOST, extends: str = "", insert: bool = True):
	doc = frappe.get_doc(
		{
			"doctype": "Settings Dialog",
			"app": app,
			"extends": extends,
			"standard": 1,
			"panes": [pane(key) if isinstance(key, str) else key for key in panes],
			"blocks": list(blocks),
		}
	)
	return doc.insert() if insert else doc


def pane(key: str, **kwargs) -> dict:
	return {"key": key, "label": key.replace("-", " ").title(), **kwargs}


def single(key: str, pane: str = "general", doctype: str = "System Settings", **kwargs) -> dict:
	return {"key": key, "pane": pane, "binding_type": "Single", "document_type": doctype, **kwargs}


def component(key: str, pane: str = "general", **kwargs) -> dict:
	return {"key": key, "pane": pane, "component": key, **kwargs}


def bound(key: str, pane: str = "general", **kwargs) -> dict:
	"""A component block on the session `User`."""
	binding = {"type": "Record", "doctype": "User", "resolver": "session_user"}
	return component(key, pane, bindings=json.dumps({"user": binding}), **kwargs)


class SettingsDialogTestCase(IntegrationTestCase):
	"""Roll back after every test: a shipped record is named for its app, so two tests would collide."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.get_doc(
			doctype="User",
			email=AUTHOR,
			first_name="Settings Author",
			roles=[{"role": "System Manager"}],
		).insert(ignore_if_duplicate=True)

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("settings_dialog_test")
		self.addCleanup(lambda: frappe.db.rollback(save_point="settings_dialog_test"))


class TestSettingsDialog(SettingsDialogTestCase):
	def test_a_shipped_record_is_named_for_its_address(self):
		with authoring():
			self.assertEqual(ship(["general"], [single("system")]).name, HOST)
			extension = ship(blocks=[single("calls")], app=EXTENDER, extends=HOST)

		self.assertEqual(extension.name, f"{EXTENDER}-{HOST}")

	def test_pane_and_block_keys_are_kebab_case(self):
		with authoring():
			for key in ("Email Accounts", "email_accounts", "-email", "email-", ""):
				with self.subTest(pane=key):
					self.assertRaises(frappe.ValidationError, ship, [pane(key)])
				with self.subTest(block=key):
					self.assertRaises(frappe.ValidationError, ship, ["general"], [single(key)])

			ship(["email-accounts"], [single("smtp-2", pane="email-accounts")])

	def test_a_pane_key_repeated_within_a_record_is_refused(self):
		with authoring():
			self.assertRaises(frappe.ValidationError, ship, ["general", "general"])

	def test_a_block_key_is_unique_within_its_pane_only(self):
		with authoring():
			self.assertRaises(
				frappe.ValidationError, ship, ["general"], [single("system"), component("system")]
			)
			ship(["general", "other"], [single("system"), single("system", pane="other")])

	def test_a_block_key_another_shipped_record_holds_in_the_pane_is_refused(self):
		with authoring():
			ship(["general"], [single("system")])
			self.assertRaises(
				frappe.ValidationError, ship, blocks=[component("system")], app=EXTENDER, extends=HOST
			)
			ship(blocks=[component("calls")], app=EXTENDER, extends=HOST)

	def test_the_host_is_refused_a_block_key_an_extension_already_holds(self):
		with authoring():
			ship(blocks=[component("calls")], app=EXTENDER, extends=HOST)
			self.assertRaises(frappe.ValidationError, ship, ["general"], [single("calls")])

	def test_a_record_of_another_host_does_not_clash(self):
		with authoring():
			ship(["general"], [single("system")])
			ship(blocks=[component("system")], app=EXTENDER, extends="elsewhere")

	def test_an_extension_may_not_add_a_pane(self):
		with authoring():
			self.assertRaises(
				frappe.ValidationError, ship, ["mine"], [component("calls")], app=EXTENDER, extends=HOST
			)

	def test_a_record_binding_names_its_resolver_from_the_closed_list(self):
		record = {"binding_type": "Record", "document_type": "User"}

		with authoring():
			self.assertRaises(frappe.ValidationError, ship, ["general"], [single("me", **record)])
			ship(["general"], [single("me", **record, name_resolver="session_user")])

	def test_a_named_binding_takes_the_same_closed_list(self):
		def named(resolver):
			binding = {"type": "Record", "doctype": "User", "resolver": resolver}
			return component("me", bindings=json.dumps({"user": binding}))

		with authoring():
			self.assertRaises(frappe.ValidationError, ship, ["general"], [named("owner")])
			ship(["general"], [named("session_user")])

	def test_a_single_binding_has_no_resolver(self):
		with authoring():
			self.assertRaises(
				frappe.ValidationError, ship, ["general"], [single("system", name_resolver="session_user")]
			)

	def test_a_hosts_block_names_one_of_its_own_panes(self):
		with authoring():
			self.assertRaises(frappe.ValidationError, ship, ["general"], [single("system", pane="gone")])
			ship(blocks=[component("calls", pane="any-host-pane")], app=EXTENDER, extends=HOST)

	def test_a_block_is_a_binding_or_a_component(self):
		with authoring():
			self.assertRaises(
				frappe.ValidationError, ship, ["general"], [single("system", component="system")]
			)
			self.assertRaises(
				frappe.ValidationError, ship, ["general"], [{"key": "empty", "pane": "general"}]
			)

	def test_a_json_column_holds_its_own_shape(self):
		cases = {
			"fields": single("system", fields='{"a": 1}'),
			"component fields": bound("photo", fields='["user_image", 1]'),
			"bindings": component("theme", bindings='["user"]'),
			"settings": component("theme", settings='"Theme"'),
			"settings label": component("theme", settings='[{"keywords": "dark"}]'),
			"settings blank label": component("theme", settings='[{"label": " ", "keywords": "dark"}]'),
			"anchors": component("theme", anchors="not json"),
			"anchor target": component("theme", anchors='[{"after": ["system"]}]'),
			"anchor parent": component("theme", anchors='[{"after": "system", "parent_key": "x"}]'),
			"binding doctype": component("theme", bindings='{"u": {"type": "Single", "doctype": ["User"]}}'),
		}

		with authoring():
			for fieldname, block in cases.items():
				with self.subTest(fieldname):
					self.assertRaises(frappe.ValidationError, ship, ["general"], [block])

			ship(
				["general"],
				[
					single("system", fields='["language", "time_zone"]'),
					component("theme", settings='[{"label": "Theme", "keywords": "dark light"}]'),
				],
			)

	def test_component_blocks_on_one_binding_share_a_save_mode(self):
		with authoring():
			self.assertRaises(
				frappe.ValidationError,
				ship,
				["general"],
				[bound("photo"), bound("signature", save_mode="button")],
			)
			ship(
				["general", "other"],
				[bound("photo"), bound("name"), bound("signature", pane="other", save_mode="button")],
			)

	def test_a_component_block_in_a_hosts_pane_shares_the_hosts_save_mode(self):
		with authoring():
			ship(["general"], [bound("photo", save_mode="button")])
			self.assertRaises(
				frappe.ValidationError, ship, blocks=[bound("calls")], app=EXTENDER, extends=HOST
			)
			ship(blocks=[bound("calls", save_mode="button")], app=EXTENDER, extends=HOST)

	def test_the_host_is_refused_a_save_mode_an_extension_already_holds(self):
		with authoring():
			ship(blocks=[bound("calls", save_mode="button")], app=EXTENDER, extends=HOST)
			self.assertRaises(frappe.ValidationError, ship, ["general"], [bound("photo")])
			ship(["general"], [bound("photo", save_mode="button")])

	def test_component_blocks_on_one_binding_declare_each_field_once(self):
		with authoring():
			self.assertRaises(
				frappe.ValidationError,
				ship,
				["general"],
				[
					bound("photo", fields='["user_image"]'),
					bound("locale", fields='["language", "user_image"]'),
				],
			)
			ship(
				["general", "other"],
				[
					bound("photo", fields='["user_image"]'),
					bound("locale", fields='["language", "time_zone"]'),
					bound("rest"),
					bound("avatar", pane="other", fields='["user_image"]'),
				],
			)

	def test_the_host_is_refused_a_field_an_extension_already_declares(self):
		with authoring():
			ship(blocks=[bound("calls", fields='["mobile_no"]')], app=EXTENDER, extends=HOST)
			self.assertRaises(
				frappe.ValidationError, ship, ["general"], [bound("phone", fields='["mobile_no"]')]
			)
			ship(["general"], [bound("phone", fields='["phone"]')])

	def test_a_generated_block_may_differ_from_a_component_on_its_binding(self):
		with authoring():
			ship(
				["general"],
				[
					single("me", doctype="User", binding_type="Record", name_resolver="session_user"),
					bound("photo", save_mode="button"),
				],
			)

	def test_app_content_is_not_writable_outside_developer_mode(self):
		with authoring(developer=False):
			self.assertRaises(frappe.ValidationError, ship, ["general"], [single("system")])

	def test_an_app_cannot_extend_itself(self):
		with authoring():
			self.assertRaises(frappe.ValidationError, ship, blocks=[component("x")], extends=HOST)

	def test_two_records_cannot_share_one_address(self):
		with authoring():
			ship(["general"], [single("system")])
			self.assertRaises(frappe.ValidationError, ship, ["other"], [single("other", pane="other")])

	def test_a_desk_user_may_not_author_settings(self):
		user = frappe.get_doc(
			doctype="User", email="settings-reader@example.com", first_name="Settings Reader"
		).insert(ignore_if_duplicate=True)
		user.add_roles("Desk User")

		with authoring(user.name):
			self.assertRaises(frappe.PermissionError, ship, ["general"], [single("system")])
