# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""An Act row a level adds, `frappe/shell/act_row.py`, through `save_arrangement` at both levels."""

import json

import frappe
from frappe.shell.arrangement import reset_arrangement, save_arrangement
from frappe.shell.navigation import resolve_navigation
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_navigation_arrangement import (
	OwnRowsTestCase,
	a_person,
	own,
	own_stored,
	showing,
	shown,
	stored,
)
from frappe.tests.test_shell_navigation import APP, NavigationTestCase, doctype_item, make_rail

KEY = "user:k3f9a2"


def an_act(payload, key: str = KEY, **kwargs) -> dict:
	return {"key": key, "item_type": "Act", "payload": payload, "label": "Theme: Dark", **kwargs}


def a_payload_of(size: int) -> dict:
	"""`{"act":"shell.theme","value":"xxx"}` padded to exactly `size` bytes."""
	bare = len(json.dumps({"act": "shell.theme", "value": ""}, separators=(",", ":")))
	return {"act": "shell.theme", "value": "x" * (size - bare)}


class TestAnActRowIsSaved(OwnRowsTestCase):
	def save(self, *added: dict, scope: str = "user"):
		return save_arrangement("Rail", APP, showing(shown("todo"), shown("note"), *added), scope=scope)

	def refused(self, payload, **kwargs):
		with self.assertRaises(frappe.ValidationError):
			self.save(an_act(payload, **kwargs))

		self.assertFalse(stored())

	def test_an_act_alone_and_an_act_with_a_value_are_accepted(self):
		for payload in ({"act": "shell.theme"}, {"act": "shell.theme", "value": "dark"}):
			with self.subTest(payload=payload):
				self.save(an_act(payload))
				self.assertEqual(json.loads(own_stored()[0].payload), payload)
				reset_arrangement("Rail", APP)

	def test_an_app_act_name_is_accepted(self):
		self.save(an_act({"act": "shell.crm.new_lead"}))

		self.assertEqual(len(own_stored()), 1)

	def test_a_site_level_row_is_accepted_too(self):
		with set_user(a_person()):
			self.save(an_act({"act": "shell.theme", "value": "dark"}, key="site:k3f9a2"), scope="site")

			self.assertIn("site:k3f9a2", [row["key"] for row in resolve_navigation(APP)["rail"]])

	def test_a_payload_of_exactly_128_bytes_is_accepted(self):
		payload = a_payload_of(128)

		self.save(an_act(payload))

		self.assertEqual(len(own_stored()[0].payload.encode()), 128)

	def test_a_payload_of_129_bytes_is_refused(self):
		self.refused(a_payload_of(129))

	def test_the_size_is_counted_in_utf8_bytes(self):
		self.refused({"act": "shell.theme", "value": "é" * 60})

	def test_a_value_that_is_not_valid_text_is_refused(self):
		self.refused({"act": "shell.theme", "value": "\ud800"})

	def test_a_spaced_out_payload_is_stored_compact(self):
		self.save(an_act('{ "act": "shell.theme", "value": "dark" }'))

		self.assertEqual(own_stored()[0].payload, '{"act":"shell.theme","value":"dark"}')

	def test_an_object_payload_is_stored_compact(self):
		self.save(an_act({"act": "shell.theme", "value": "é"}))

		self.assertEqual(own_stored()[0].payload, '{"act":"shell.theme","value":"é"}')

	def test_a_payload_that_is_not_an_object_is_refused(self):
		for payload in ('["shell.theme"]', '"shell.theme"', "not json", "[]"):
			with self.subTest(payload=payload):
				self.refused(payload)

	def test_a_payload_with_no_act_is_refused(self):
		for payload in (None, "", {}, {"value": "dark"}):
			with self.subTest(payload=payload):
				self.refused(payload)

	def test_an_act_that_is_not_a_shell_act_is_refused(self):
		for name in ("theme", "app.theme", "shell.", "shell.Theme", "shell.a.b.c", "shell.a-b", 7, None):
			with self.subTest(name=name):
				self.refused({"act": name})

	def test_a_payload_with_an_extra_key_is_refused(self):
		self.refused({"act": "shell.theme", "label": "x"})


class TestAnActRowOpensNoSidebar(OwnRowsTestCase):
	def test_a_save_refuses_an_act_that_opens_a_sidebar(self):
		row = an_act({"act": "shell.theme"}, opens_sidebar="site:abc123")

		with self.assertRaisesRegex(frappe.ValidationError, "can't open a sidebar"):
			save_arrangement("Rail", APP, showing(shown("todo"), row))

		self.assertFalse(stored())


class TestAnActRowSurvivesTheFilter(NavigationTestCase):
	def test_a_person_with_no_roles_sees_an_act_row(self):
		email = "act_row_no_roles@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				doctype="User", email=email, first_name="Act", user_type="System User", roles=[]
			).insert(ignore_permissions=True)
		self.addCleanup(frappe.clear_cache, user=email)

		make_rail(
			[
				doctype_item("secret", "Role"),
				{
					"doctype": "Navigation Item",
					"key": "theme",
					"item_type": "Act",
					"payload": json.dumps({"act": "shell.theme"}),
				},
			],
			standard=1,
		)

		with set_user(email):
			keys = [row["key"] for row in resolve_navigation(APP)["rail"]]

		self.assertEqual(keys, ["theme"])
