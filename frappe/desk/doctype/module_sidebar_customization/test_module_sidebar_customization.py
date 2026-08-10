# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.boot import get_module_sidebars
from frappe.desk.doctype.module_sidebar.test_module_sidebar import make_report, sidebarless_module
from frappe.desk.doctype.module_sidebar_customization.module_sidebar_customization import (
	CUSTOMIZED_KEYS_CACHE_KEY,
	get_customized_keys,
	reset_user_sidebar,
	save_sidebar_customization,
	save_site_sidebar,
)
from frappe.tests import IntegrationTestCase

MODULE = "Core"
USER = "test-sidebar-custom@example.com"


class TestModuleSidebarCustomization(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": USER,
					"first_name": "Custom",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert()
		self.wipe()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.wipe()
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)

	def wipe(self):
		frappe.db.delete("Module Sidebar Customization", {"module": MODULE})
		frappe.cache.delete_value(CUSTOMIZED_KEYS_CACHE_KEY)
		frappe.clear_cache(user=USER)

	def base_items(self):
		frappe.set_user("Administrator")
		return get_module_sidebars()[MODULE]["items"]

	def as_user(self):
		frappe.set_user(USER)

	def test_uncustomized_module_costs_no_query(self):
		"""The cost-control story: an uncustomized site pays one redis read, not a query per
		module."""
		self.assertEqual(get_customized_keys(), set())
		sidebars = get_module_sidebars()
		self.assertEqual(sidebars[MODULE].get("customized"), 0)

	def test_hidden_item_disappears(self):
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"item_key": target["key"], "hidden": 1}]))

		keys = [i["key"] for i in get_module_sidebars()[MODULE]["items"]]
		self.assertNotIn(target["key"], keys)

	def test_rename_and_icon_override(self):
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(
			MODULE,
			json.dumps([{"item_key": target["key"], "label": "Renamed", "icon": "star"}]),
		)

		item = next(i for i in get_module_sidebars()[MODULE]["items"] if i["key"] == target["key"])
		self.assertEqual(item["label"], "Renamed")
		self.assertEqual(item["icon"], "star")

	def test_reorder_puts_named_items_first(self):
		"""Base items the user never arranged keep their order and follow the ones they did, so
		an app adding an item still surfaces for someone who has already reordered."""
		items = self.base_items()
		last = items[-1]

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"item_key": last["key"]}]))

		resolved = get_module_sidebars()[MODULE]["items"]
		self.assertEqual(resolved[0]["key"], last["key"])

	def test_unknown_key_is_skipped_not_errored(self):
		"""What makes an app re-authoring its sidebar non-fatal."""
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"item_key": "no-such-key-000", "hidden": 1}]))

		self.assertTrue(get_module_sidebars()[MODULE]["items"])

	def test_hiding_everything_hides_the_module(self):
		"""The "no non-Section-Break item survives" rule runs after the deltas."""
		items = self.base_items()
		prefs = [{"item_key": i["key"], "hidden": 1} for i in items]

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps(prefs))

		self.assertNotIn(MODULE, get_module_sidebars())

	def test_user_layer_overrides_site_layer(self):
		"""A user's `hidden: 0` un-hides what the site hid -- a preference beating a
		preference, which is what a per-user layer is for."""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		save_site_sidebar(MODULE, json.dumps([{"item_key": target["key"], "hidden": 1}]))

		self.as_user()
		# site layer applies to this user...
		self.assertNotIn(target["key"], [i["key"] for i in get_module_sidebars()[MODULE]["items"]])

		save_sidebar_customization(MODULE, json.dumps([{"item_key": target["key"], "hidden": 0}]))
		self.assertIn(target["key"], [i["key"] for i in get_module_sidebars()[MODULE]["items"]])

	def test_added_item_appears(self):
		self.as_user()
		save_sidebar_customization(
			MODULE,
			json.dumps([]),
			json.dumps([{"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Mine"}]),
		)

		labels = [i["label"] for i in get_module_sidebars()[MODULE]["items"]]
		self.assertIn("Mine", labels)

	def test_reset_restores_the_base(self):
		# baseline read as the same user, since the item set is permission-filtered per user
		self.as_user()
		before = [i["key"] for i in get_module_sidebars()[MODULE]["items"]]
		target = next(i for i in get_module_sidebars()[MODULE]["items"] if i["type"] != "Section Break")

		save_sidebar_customization(MODULE, json.dumps([{"item_key": target["key"], "hidden": 1}]))
		self.assertNotEqual(before, [i["key"] for i in get_module_sidebars()[MODULE]["items"]])

		reset_user_sidebar(MODULE)
		self.assertEqual(before, [i["key"] for i in get_module_sidebars()[MODULE]["items"]])

	def test_another_user_is_unaffected(self):
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"item_key": target["key"], "hidden": 1}]))

		frappe.set_user("Administrator")
		self.assertIn(target["key"], [i["key"] for i in get_module_sidebars()[MODULE]["items"]])

	def test_delta_cannot_resurface_a_forbidden_item(self):
		"""Deltas are applied after the permission filter, so an item the user may not see is
		not in the list a delta can reorder or un-hide."""
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"item_key": "some-forbidden-key", "hidden": 0}]))

		keys = [i["key"] for i in get_module_sidebars()[MODULE]["items"]]
		self.assertNotIn("some-forbidden-key", keys)


class TestCustomizationTarget(IntegrationTestCase):
	"""What a customization has to be *of*.

	Not a `Module Sidebar`: most modules have no document at all, their base being computed
	from their contents, and those are exactly as customizable as a shipped one. The module is
	the thing that has to exist.
	"""

	def setUp(self):
		frappe.set_user("Administrator")

	def test_a_module_with_no_sidebar_document_can_be_customized(self):
		module = "Test Customizable Computed Module"
		self.addCleanup(frappe.db.delete, "Module Sidebar Customization", {"module": module})

		with sidebarless_module(module):
			doomed = make_report(module, "Test Customizable Report")
			# a second one, so hiding the first leaves something navigable behind -- a module
			# with nothing left but its section headers is dropped from the payload entirely
			survivor = make_report(module, "Test Surviving Customizable Report")

			# by link, not by position: a computed base leads with a section header
			def key_for(name):
				return next(i["key"] for i in get_module_sidebars()[module]["items"] if i["link_to"] == name)

			save_sidebar_customization(module, json.dumps([{"item_key": key_for(doomed.name), "hidden": 1}]))

			links = [i["link_to"] for i in get_module_sidebars()[module]["items"]]
			self.assertNotIn(doomed.name, links)
			self.assertIn(survivor.name, links)

	def test_a_module_that_does_not_exist_cannot_be_customized(self):
		"""Asserted on the message, because the child table's own Link validation would raise
		a `ValidationError` too -- and that one fires only after the write has been assembled."""
		with self.assertRaises(frappe.ValidationError) as caught:
			save_sidebar_customization("Test No Such Module", json.dumps([]))

		self.assertIn("is not a module", str(caught.exception))
