# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.boot import get_module_sidebars
from frappe.desk.doctype.custom_module_sidebar.custom_module_sidebar import (
	CUSTOMIZED_KEYS_CACHE_KEY,
	get_customization,
	get_customized_keys,
	reset_user_sidebar,
	save_sidebar_customization,
	save_site_sidebar,
)
from frappe.desk.doctype.module_sidebar.test_module_sidebar import make_report, sidebarless_module
from frappe.tests import IntegrationTestCase

MODULE = "Core"
USER = "test-sidebar-custom@example.com"
MANAGER = "test-sidebar-manager@example.com"


def make_user(email: str, roles: list[str]):
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	return frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in roles],
		}
	).insert(ignore_permissions=True)


class CustomizationTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		make_user(USER, ["System Manager"])
		self.wipe()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.wipe()
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)

	def wipe(self, module: str = MODULE):
		for name in frappe.get_all("Custom Module Sidebar", filters={"module": module}, pluck="name"):
			frappe.delete_doc("Custom Module Sidebar", name, force=True, ignore_permissions=True)
		frappe.cache.delete_value(CUSTOMIZED_KEYS_CACHE_KEY)
		frappe.clear_cache(user=USER)

	def base_items(self, module: str = MODULE):
		frappe.set_user("Administrator")
		return get_module_sidebars()[module]["items"]

	def items(self, module: str = MODULE):
		return get_module_sidebars()[module]["items"]

	def keys(self, module: str = MODULE):
		return [item["key"] for item in self.items(module)]

	def as_user(self):
		frappe.set_user(USER)


class TestModuleSidebarCustomization(CustomizationTestCase):
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
		save_sidebar_customization(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		self.assertNotIn(target["key"], self.keys())

	def test_rename_and_icon_override(self):
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(
			MODULE,
			json.dumps([{"key": target["key"], "label": "Renamed", "icon": "star"}]),
		)

		item = next(i for i in self.items() if i["key"] == target["key"])
		self.assertEqual(item["label"], "Renamed")
		self.assertEqual(item["icon"], "star")

	def test_reorder_puts_named_items_first(self):
		"""Base items the layer never named keep their order and follow the ones it did, so an
		app adding an item still surfaces for someone who has already reordered."""
		items = self.base_items()
		last = items[-1]

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": last["key"]}]))

		self.assertEqual(self.keys()[0], last["key"])

	def test_unknown_key_is_skipped_not_errored(self):
		"""What makes an app re-authoring its sidebar non-fatal, and what an item the app has
		since deleted meets."""
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": "no-such-key-000", "hidden": 1}]))

		self.assertTrue(self.items())

	def test_hiding_everything_hides_the_module(self):
		"""The "no non-Section-Break item survives" rule runs after the layers."""
		rows = [{"key": item["key"], "hidden": 1} for item in self.base_items()]

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps(rows))

		self.assertNotIn(MODULE, get_module_sidebars())

	def test_user_layer_overrides_site_layer(self):
		"""A user's `hidden: 0` un-hides what the site hid -- which is the whole reason `hidden`
		is a field rather than the row's presence."""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		save_site_sidebar(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		self.as_user()
		# the site layer applies to this user...
		self.assertNotIn(target["key"], self.keys())

		save_sidebar_customization(MODULE, json.dumps([{"key": target["key"], "hidden": 0}]))
		self.assertIn(target["key"], self.keys())

	def test_added_item_appears(self):
		self.as_user()
		save_sidebar_customization(
			MODULE,
			json.dumps(
				[{"added": 1, "type": "Link", "link_type": "DocType", "link_to": "User", "label": "Mine"}]
			),
		)

		self.assertIn("Mine", [item["label"] for item in self.items()])

	def test_an_added_item_sits_where_it_was_put(self):
		"""One ordered table for references and additions alike, which is what stops an added
		item being pinned to the end of the list."""
		items = self.base_items()
		first, second = items[0], items[1]

		self.as_user()
		save_sidebar_customization(
			MODULE,
			json.dumps(
				[
					{"key": first["key"]},
					{"added": 1, "type": "Link", "link_type": "DocType", "link_to": "User", "label": "Mine"},
					{"key": second["key"]},
				]
			),
		)

		labels = [item["label"] for item in self.items()]
		self.assertEqual(labels[1], "Mine")

	def test_reset_restores_the_base(self):
		# baseline read as the same user, since the item set is permission-filtered per user
		self.as_user()
		before = self.keys()
		target = next(i for i in self.items() if i["type"] != "Section Break")

		save_sidebar_customization(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))
		self.assertNotEqual(before, self.keys())

		# no admin involved: a user can always get back to what everyone else sees
		reset_user_sidebar(MODULE)
		self.assertEqual(before, self.keys())

	def test_another_user_is_unaffected(self):
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		frappe.set_user("Administrator")
		self.assertIn(target["key"], self.keys())

	def test_delta_cannot_resurface_a_forbidden_item(self):
		"""Layers are applied after the permission filter, so an item the user may not see is
		not in the list a layer can reorder or un-hide."""
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": "some-forbidden-key", "hidden": 0}]))

		self.assertNotIn("some-forbidden-key", self.keys())

	def test_the_module_label_and_header_icon_are_customizable(self):
		save_site_sidebar(MODULE, label="Site Label", header_icon="star")

		self.as_user()
		sidebar = get_module_sidebars()[MODULE]
		self.assertEqual(sidebar["label"], "Site Label")
		self.assertEqual(sidebar["header_icon"], "star")

		save_sidebar_customization(MODULE, label="My Label")
		self.assertEqual(get_module_sidebars()[MODULE]["label"], "My Label")


class TestAReorderIsNotAnOpinionAboutEverything(CustomizationTestCase):
	"""The failure mode that killed storing full item bodies against base items.

	The client saves the arrangement it is *showing*, labels and all. Stored as they arrive,
	one reorder would freeze every label the user happened to be looking at -- so the site's
	relabel and the app's next release would never reach them again.
	"""

	def test_an_item_the_user_never_touched_keeps_following_the_site_and_the_app(self):
		with sidebarless_module("Test Following Module") as module:
			make_report(module, "Test Following Report A")
			make_report(module, "Test Following Report B")
			self.addCleanup(self.wipe, module)

			frappe.set_user("Administrator")
			items = self.items(module)
			followed = next(i for i in items if i["link_to"] == "Test Following Report A")

			# the user reorders -- sending back the whole arrangement, labels included, the way
			# a Sortable does
			self.as_user()
			save_sidebar_customization(module, json.dumps(list(reversed(items))))

			# nothing of the site's is stored as the user's own opinion
			layer = get_customization(module, USER)
			self.assertTrue(all(not row.label and not row.icon for row in layer.sidebar_items))

			# ... and now the site relabels an item, and the app ships another one
			frappe.set_user("Administrator")
			save_site_sidebar(module, json.dumps([{"key": followed["key"], "label": "Site Renamed"}]))
			make_report(module, "Test Following Report C")
			# what installing the app would do: the set of reports a user may see is cached for
			# six hours, so without this the new item is invisible to everyone but Administrator
			# for reasons that have nothing to do with the layers under test
			frappe.clear_cache()

			self.as_user()
			resolved = self.items(module)
			relabelled = next(i for i in resolved if i["key"] == followed["key"])
			self.assertEqual(relabelled["label"], "Site Renamed")
			self.assertIn("Test Following Report C", [i["link_to"] for i in resolved])

	def test_a_relabel_the_user_did_mean_is_kept(self):
		"""The other half: only values that merely echo what the user was shown are dropped."""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(
			MODULE,
			json.dumps([{**item, "label": "Mine"} if item is target else item for item in items]),
		)

		item = next(i for i in self.items() if i["key"] == target["key"])
		self.assertEqual(item["label"], "Mine")


class TestWhoMayTouchTheSiteLayer(CustomizationTestCase):
	"""`Workspace Manager`, not System Manager -- the role literally named for curating
	navigation, granted to nobody by default."""

	def setUp(self):
		super().setUp()
		make_user(MANAGER, ["Desk User", "Workspace Manager"])

	def tearDown(self):
		super().tearDown()
		frappe.delete_doc("User", MANAGER, force=True, ignore_missing=True)

	def test_a_desk_user_cannot_write_the_site_layer(self):
		self.as_user()
		self.assertNotIn("Workspace Manager", frappe.get_roles())

		with self.assertRaises(frappe.PermissionError):
			save_site_sidebar(MODULE, json.dumps([]))

	def test_a_desk_user_cannot_write_the_site_layer_from_the_form_either(self):
		"""The endpoint is not the only door: without a document-level gate a plain user could
		write the site layer straight from the doctype."""
		self.as_user()
		doc = frappe.get_doc({"doctype": "Custom Module Sidebar", "module": MODULE, "user": ""})

		with self.assertRaises(frappe.PermissionError):
			doc.insert()

	def test_a_desk_user_may_write_their_own_layer_from_the_form(self):
		self.as_user()
		doc = frappe.get_doc(
			{"doctype": "Custom Module Sidebar", "module": MODULE, "user": frappe.session.user}
		).insert()

		self.assertTrue(frappe.db.exists("Custom Module Sidebar", doc.name))

	def test_a_workspace_manager_can_write_the_site_layer(self):
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		frappe.set_user(MANAGER)
		save_site_sidebar(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		self.as_user()
		self.assertNotIn(target["key"], self.keys())

	def test_one_users_preferences_stay_out_of_another_users_reads(self):
		"""Nobody but a Workspace Manager reads anyone else's arrangement. The manager reads
		everything -- and the list view's default filter is what keeps a site audit, and the
		export that follows it, to the site layer alone."""
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([]))

		frappe.set_user(MANAGER)
		save_site_sidebar(MODULE, json.dumps([]))
		self.assertEqual(
			{row.user for row in frappe.get_list("Custom Module Sidebar", fields=["user"])},
			{"", USER},
		)

		self.as_user()
		self.assertEqual(
			{row.user for row in frappe.get_list("Custom Module Sidebar", fields=["user"])},
			{USER},
		)


class TestUserRowsAreTheUsers(CustomizationTestCase):
	def test_deleting_a_user_takes_their_arrangement_with_them(self):
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([]))
		frappe.set_user("Administrator")
		save_site_sidebar(MODULE, json.dumps([]))

		self.assertTrue(frappe.db.exists("Custom Module Sidebar", {"user": USER}))

		frappe.delete_doc("User", USER, force=True, ignore_permissions=True)

		self.assertFalse(frappe.db.exists("Custom Module Sidebar", {"user": USER}))
		# the site layer is nobody's personal preference
		self.assertTrue(frappe.db.exists("Custom Module Sidebar", {"user": ""}))


class TestTheModelSaysWhatItMeans(IntegrationTestCase):
	def test_the_old_tables_are_gone(self):
		"""One child table serves base, site and user; the preference table and the separate
		added-items table have nothing left to hold.

		Asserted on the app rather than the site: a doctype is gone when it stops being shipped,
		and `remove_orphan_doctypes` drops the row on the next migrate.
		"""
		import os

		self.assertFalse(
			os.path.exists(frappe.get_app_path("frappe", "desk", "doctype", "module_sidebar_item_preference"))
		)

		fieldnames = {df.fieldname for df in frappe.get_meta("Custom Module Sidebar").fields}
		self.assertIn("sidebar_items", fieldnames)
		self.assertNotIn("items", fieldnames)
		self.assertNotIn("added_items", fieldnames)

	def test_the_child_carries_both_flags(self):
		fieldnames = {df.fieldname for df in frappe.get_meta("Module Sidebar Item").fields}

		self.assertIn("hidden", fieldnames)
		self.assertIn("added", fieldnames)

	def test_the_doctype_records_why_it_holds_user_rows(self):
		"""The `Custom *` prefix means site-owned everywhere else in the repo. The next reader
		has to find out why this one is different before they "fix" it."""
		description = frappe.db.get_value("DocType", "Custom Module Sidebar", "description") or ""

		self.assertIn("user", description)
		self.assertIn("site layer", description)


class TestCustomizationTarget(CustomizationTestCase):
	"""What a customization has to be *of*.

	Not a `Module Sidebar`: most modules have no document at all, their base being computed
	from their contents, and those are exactly as customizable as a shipped one. The module is
	the thing that has to exist.
	"""

	def test_a_module_with_no_sidebar_document_can_be_customized(self):
		module = "Test Customizable Computed Module"
		self.addCleanup(self.wipe, module)

		with sidebarless_module(module):
			doomed = make_report(module, "Test Customizable Report")
			# a second one, so hiding the first leaves something navigable behind -- a module
			# with nothing left but its section headers is dropped from the payload entirely
			survivor = make_report(module, "Test Surviving Customizable Report")

			# by link, not by position: a computed base leads with a section header
			def key_for(name):
				return next(i["key"] for i in self.items(module) if i["link_to"] == name)

			save_sidebar_customization(module, json.dumps([{"key": key_for(doomed.name), "hidden": 1}]))

			links = [i["link_to"] for i in self.items(module)]
			self.assertNotIn(doomed.name, links)
			self.assertIn(survivor.name, links)

	def test_a_module_that_does_not_exist_cannot_be_customized(self):
		"""Asserted on the message, because the child table's own Link validation would raise
		a `ValidationError` too -- and that one fires only after the write has been assembled."""
		with self.assertRaises(frappe.ValidationError) as caught:
			save_sidebar_customization("Test No Such Module", json.dumps([]))

		self.assertIn("is not a module", str(caught.exception))
