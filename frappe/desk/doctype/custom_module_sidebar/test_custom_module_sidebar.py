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
from frappe.desk.doctype.module_sidebar.test_module_sidebar import (
	delete_page,
	make_page,
	make_report,
	no_developer_mode,
	sidebarless_module,
)
from frappe.tests import IntegrationTestCase

# Any module the dock can take you to will do -- these tests are about the layers, not about
# this module. Not `Core`: it is a `code_only_modules` module now, so `get_navigable_modules`
# skips it and the payload has no key for it at all.
MODULE = "Users"
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


class TestIdentityIsMadeOfRealColumns(CustomizationTestCase):
	"""D7: a customization survives a rename, and nothing else re-anchors it.

	A delta row and the base row it names are both `Module Sidebar Item` rows carrying a
	Dynamic Link, so `rename_dynamic_links` rewrites the pair in one statement -- no hook, no
	patch, no re-keying. These pin that, and the things that used to move an anchor and now
	must not.
	"""

	def test_renaming_a_linked_target_moves_base_and_delta_together(self):
		"""A Page rather than a Report, because a Report cannot be renamed at all."""
		with sidebarless_module("Test Renamed Target Module") as module:
			self.addCleanup(self.wipe, module)
			doomed = make_page(module, "test-renamed-page")
			# something else navigable, so hiding the page does not drop the module entirely
			make_report(module, "Test Bystander Report")

			self.as_user()
			hidden = next(i for i in self.items(module) if i["link_to"] == doomed.name)
			save_sidebar_customization(module, json.dumps([{**hidden, "hidden": 1}]))
			self.assertNotIn(doomed.name, [i["link_to"] for i in self.items(module)])

			frappe.set_user("Administrator")
			frappe.rename_doc("Page", doomed.name, "test-renamed-page-again")

			self.as_user()
			links = [i["link_to"] for i in self.items(module)]
			self.assertIn("Test Bystander Report", links, "sanity: the module still resolves")
			self.assertNotIn(
				"test-renamed-page-again",
				links,
				"the delta stopped naming its item across the rename",
			)

	def test_the_delta_stores_the_link_rather_than_an_id(self):
		"""What makes the repair reach it: the stored row carries the real columns, so the
		rename's `UPDATE ... SET link_to` finds it like any other Dynamic Link."""
		with sidebarless_module("Test Stored Columns Module") as module:
			self.addCleanup(self.wipe, module)
			report = make_report(module, "Test Stored Columns Report")

			self.as_user()
			target = next(i for i in self.items(module) if i["link_to"] == report.name)
			# the shorthand a client may send: the key alone, no columns. What is *stored* is
			# canonical either way, or the guarantee would depend on how the client asked.
			save_sidebar_customization(module, json.dumps([{"key": target["key"], "hidden": 1}]))

			row = get_customization(module, USER).sidebar_items[0]
			self.assertEqual((row.link_type, row.link_to), ("Report", report.name))
			self.assertFalse(row.key, "a linked row stores no id beside its columns")

	def test_hiding_an_item_does_not_stop_anyone_deleting_it(self):
		"""The price of storing a real Dynamic Link: a link blocks a delete, unless the model
		says this kind of link is not a reference. It is not -- a sidebar item is a way in, and
		a dangling one is already skipped on read -- so a person hiding something in their own
		sidebar must not be able to stop an admin deleting it.
		"""
		with sidebarless_module("Test Deletable Target Module") as module:
			self.addCleanup(self.wipe, module)
			doomed = make_page(module, "test-deletable-page")
			make_report(module, "Test Deletable Bystander")

			self.as_user()
			target = next(i for i in self.items(module) if i["link_to"] == doomed.name)
			save_sidebar_customization(module, json.dumps([{**target, "hidden": 1}]))

			frappe.set_user("Administrator")
			delete_page(doomed.name)

			self.assertFalse(frappe.db.exists("Page", doomed.name))

	def test_a_stale_reference_does_not_block_the_next_write(self):
		"""The other half of the same price: a stored link is *validated* on save, so a row
		left naming a deleted item would turn every later write to that layer into a link
		error -- renaming the sidebar, adding a workspace's link, anything.

		It stops applying, which is what an item the app has deleted has always done. It does
		not stop the layer being written.
		"""
		with sidebarless_module("Test Stale Reference Module") as module:
			self.addCleanup(self.wipe, module)
			doomed = make_page(module, "test-stale-page")
			make_report(module, "Test Stale Bystander")

			target = next(i for i in self.base_items(module) if i["link_to"] == doomed.name)
			save_site_sidebar(module, json.dumps([{**target, "hidden": 1}]))
			delete_page(doomed.name)

			# an unrelated write to the same layer, which saves the stale row along with it
			save_site_sidebar(module, label="Renamed Module")

			self.assertEqual(get_module_sidebars()[module]["label"], "Renamed Module")

	def test_inserting_an_item_does_not_re_anchor_other_deltas(self):
		"""The ordinal is gone, and with it the thing that made an insertion move every anchor
		below it."""
		with sidebarless_module("Test Insertion Module") as module:
			self.addCleanup(self.wipe, module)
			make_report(module, "Test Insertion Report A")
			hidden = make_report(module, "Test Insertion Report B")

			self.as_user()
			target = next(i for i in self.items(module) if i["link_to"] == hidden.name)
			save_sidebar_customization(module, json.dumps([{**target, "hidden": 1}]))

			frappe.set_user("Administrator")
			make_report(module, "Test Insertion Report C")
			frappe.clear_cache()

			self.as_user()
			links = [i["link_to"] for i in self.items(module)]
			self.assertNotIn(hidden.name, links, "an unrelated insertion moved the anchor")
			self.assertIn("Test Insertion Report C", links)

	def test_a_section_break_still_matches_across_a_recomputation(self):
		"""An unlinked row has nothing to repair, so it keeps a stored key -- hashed from its
		type and label, both of which a recomputation reproduces exactly."""
		with sidebarless_module("Test Section Module") as module:
			self.addCleanup(self.wipe, module)
			make_report(module, "Test Section Report A")

			section = next(i for i in self.base_items(module) if i["type"] == "Section Break")
			save_site_sidebar(module, json.dumps([{**section, "label": "Renamed Section"}]))

			# the module gains content, so its base is computed again from scratch
			make_report(module, "Test Section Report B")
			frappe.clear_cache()

			self.as_user()
			labels = [i["label"] for i in self.items(module) if i["type"] == "Section Break"]
			self.assertIn("Renamed Section", labels)


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


class TestNoLayerHoldsAPrivatePage(CustomizationTestCase):
	"""A private workspace's link is derived on read, so no layer ever stores one.

	The derivation is appended to the arrangement the client is shown, which means the client
	sends it straight back on the next save. Kept, the site layer would fill up with one row
	per private page of whoever last curated it -- exactly the pollution D3 removes -- and the
	owner's own layer would hold a second copy of a link that is already derived from the
	workspace.
	"""

	def make_workspace(self, title, public, for_user=""):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": f"{title}-{for_user}" if for_user else title,
				"module": MODULE,
				"public": public,
				"for_user": for_user,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		return doc

	def stored_links(self, user=None):
		layer = get_customization(MODULE, user)
		return [row.link_to for row in layer.sidebar_items] if layer else []

	def row_for(self, workspace):
		return {
			"added": 1,
			"type": "Link",
			"link_type": "Workspace",
			"link_to": workspace.name,
			"label": workspace.title,
		}

	def test_the_site_layer_drops_a_row_naming_a_private_page(self):
		private = self.make_workspace("Test Site Layer Private Page", public=0, for_user=USER)
		public = self.make_workspace("Test Site Layer Public Page", public=1)

		save_site_sidebar(MODULE, json.dumps([self.row_for(private), self.row_for(public)]))

		self.assertEqual(self.stored_links(), [public.name])

	def test_the_owners_own_layer_drops_it_too(self):
		"""Their own page, but still not their own row: it is derived from the workspace, and a
		stored copy would outlive the page it names."""
		private = self.make_workspace("Test Own Layer Private Page", public=0, for_user=USER)

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([self.row_for(private)]))

		self.assertEqual(self.stored_links(USER), [])

	def test_a_page_that_turns_private_takes_its_stored_row_out_on_the_next_save(self):
		"""What retires the rows a site stored before the derivation existed: every write runs
		the rule, so the next save of that layer takes them with it."""
		workspace = self.make_workspace("Test Turned Private Page", public=1)
		save_site_sidebar(MODULE, json.dumps([self.row_for(workspace)]))
		self.assertEqual(self.stored_links(), [workspace.name])

		frappe.db.set_value("Workspace", workspace.name, {"public": 0, "for_user": USER})
		save_site_sidebar(MODULE, label="Renamed")

		self.assertEqual(self.stored_links(), [])


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

	def test_deleting_the_module_takes_its_customizations_with_it(self):
		"""A layer is anchored to a module, so it goes when the module does -- the same rule
		the sidebar document already follows.

		It has to be said out loud now. A Link used to refuse the delete on the row's behalf,
		and navigation links no longer do: `ignore_links_on_delete` covers this doctype so that
		nobody's sidebar preference can stop a document being deleted. Refusing was never the
		right answer for a module either -- deleting one now cleans up after itself.
		"""
		module = "Test Deleted Module With Customization"
		with no_developer_mode():
			frappe.get_doc({"doctype": "Module Def", "module_name": module, "app_name": "frappe"}).insert()

		save_site_sidebar(module, json.dumps([]))
		self.assertTrue(frappe.db.exists("Custom Module Sidebar", {"module": module}))

		with no_developer_mode():
			frappe.delete_doc("Module Def", module)

		self.assertFalse(frappe.db.exists("Custom Module Sidebar", {"module": module}))

	def test_a_module_that_does_not_exist_cannot_be_customized(self):
		"""Asserted on the message, because the child table's own Link validation would raise
		a `ValidationError` too -- and that one fires only after the write has been assembled."""
		with self.assertRaises(frappe.ValidationError) as caught:
			save_sidebar_customization("Test No Such Module", json.dumps([]))

		self.assertIn("is not a module", str(caught.exception))
