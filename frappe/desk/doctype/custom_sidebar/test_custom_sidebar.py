# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.doctype.custom_sidebar.custom_sidebar import (
	get_customization,
	get_layers_for,
	get_site_sidebar_layer,
	get_user_sidebar_layer,
	remove_workspace_rows,
	reset_site_sidebar,
	reset_to_standard,
	reset_user_sidebar,
	save_sidebar_customization,
	save_site_sidebar,
)
from frappe.desk.doctype.sidebar.sidebar import item_key, resolve_sidebar, unlinked_key
from frappe.desk.doctype.sidebar.test_sidebar import (
	delete_page,
	developer_mode,
	make_page,
	make_report,
	no_developer_mode,
	sidebarless_module,
)
from frappe.desk.doctype.workspace.workspace import PRIVATE_MODULE, add_to_sidebar, ensure_module
from frappe.tests import IntegrationTestCase

# Any module the dock can take you to will do, since these tests are about the layers rather than
# this module. Not `Core`: it is a `code_only_modules` module now, so `get_navigable_modules`
# skips it and the payload has no key for it.
MODULE = "Users"
USER = "test-sidebar-custom@example.com"
MANAGER = "test-sidebar-manager@example.com"
OTHER = "test-sidebar-other@example.com"


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
		for name in frappe.get_all("Custom Sidebar", filters={"module": module}, pluck="name"):
			frappe.delete_doc("Custom Sidebar", name, force=True, ignore_permissions=True)
		frappe.clear_cache(user=USER)

	def resolved(self, module: str = MODULE):
		"""What `module` resolves to for the session user, which is where every layer lands."""
		return resolve_sidebar(module, frappe.session.user)

	def base_items(self, module: str = MODULE):
		frappe.set_user("Administrator")
		return self.resolved(module).items

	def items(self, module: str = MODULE):
		return self.resolved(module).items

	def keys(self, module: str = MODULE):
		return [item["key"] for item in self.items(module)]

	def as_user(self):
		frappe.set_user(USER)


class TestSidebarCustomization(CustomizationTestCase):
	def test_an_uncustomized_module_has_no_layers(self):
		"""Nothing is stored for it at either level, so nothing is applied to it."""
		self.assertEqual(get_layers_for(frappe.session.user, [MODULE]), {})
		self.assertFalse(self.resolved().customized)

	def test_the_layers_cost_one_query_however_many_modules(self):
		"""The cost-control claim, stated as what is true: which layers apply depends on the user, so
		it is asked once per resolution rather than once per module. It is asserted against a real set
		of modules, because the failure this guards against is a lookup that quietly moved back inside
		the loop.
		"""
		from frappe.desk.doctype.sidebar.sidebar import get_navigable_modules

		modules = get_navigable_modules()
		self.assertGreater(len(modules), 1, "sanity: more than one module to batch")

		with self.assertQueryCount(1):
			get_layers_for(frappe.session.user, modules)

	def test_a_layer_is_found_however_the_site_row_spells_unset(self):
		"""A blank Link stores as `''` or as NULL depending on how the row was written, and both
		spellings are the site layer.
		"""
		save_site_sidebar(MODULE, json.dumps([]), label="Site Says")
		name = frappe.db.get_value("Custom Sidebar", {"module": MODULE})
		frappe.db.set_value("Custom Sidebar", name, "user", None, update_modified=False)
		frappe.clear_cache()

		layers = get_layers_for(USER, [MODULE])

		self.assertEqual([layer.name for layer in layers.get(MODULE, [])], [name])

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
		"""Base items the layer never named keep their order and follow the ones it did, so an app
		adding an item still reaches someone who has already reordered.
		"""
		items = self.base_items()
		last = items[-1]

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": last["key"]}]))

		self.assertEqual(self.keys()[0], last["key"])

	def test_unknown_key_is_skipped_not_errored(self):
		"""What makes an app re-authoring its sidebar non-fatal, and what happens to an item the app
		has since deleted.
		"""
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": "no-such-key-000", "hidden": 1}]))

		self.assertTrue(self.items())

	def test_hiding_everything_hides_the_module(self):
		"""The "no non-Section-Break item survives" rule runs after the layers."""
		rows = [{"key": item["key"], "hidden": 1} for item in self.base_items()]

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps(rows))

		self.assertIsNone(self.resolved())

	def test_user_layer_overrides_site_layer(self):
		"""A user's `hidden: 0` un-hides what the site hid, which is why `hidden` is a field rather
		than the row's presence.
		"""
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
		"""One ordered table for references and additions alike, which is what stops an added item
		being pinned to the end of the list.
		"""
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
		"""Layers are applied after the permission filter, so an item the user may not see is not in
		the list a layer can reorder or un-hide.
		"""
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": "some-forbidden-key", "hidden": 0}]))

		self.assertNotIn("some-forbidden-key", self.keys())

	def test_the_module_label_and_header_icon_are_customizable(self):
		save_site_sidebar(MODULE, label="Site Label", header_icon="star")

		self.as_user()
		sidebar = self.resolved()
		self.assertEqual(sidebar.label, "Site Label")
		self.assertEqual(sidebar.header_icon, "star")

		save_sidebar_customization(MODULE, label="My Label")
		self.assertEqual(self.resolved().label, "My Label")


class TestAReorderIsNotAnOpinionAboutEverything(CustomizationTestCase):
	"""The failure mode that ruled out storing full item bodies against base items.

	The client saves the arrangement it is showing, labels and all. Stored as they arrive, one
	reorder would freeze every label the user happened to be looking at, so the site's relabel and
	the app's next release would never reach them again.

	"""

	def test_an_item_the_user_never_touched_keeps_following_the_site_and_the_app(self):
		with sidebarless_module("Test Following Module") as module:
			make_report(module, "Test Following Report A")
			make_report(module, "Test Following Report B")
			self.addCleanup(self.wipe, module)

			frappe.set_user("Administrator")
			items = self.items(module)
			followed = next(i for i in items if i["link_to"] == "Test Following Report A")

			# The user reorders, sending back the whole arrangement, labels included, the way a
			# Sortable does.
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

	A delta row and the base row it names are both `Sidebar Item` rows carrying a Dynamic Link, so
	`rename_dynamic_links` rewrites the pair in one statement, with no hook, patch or re-keying.
	These tests pin that, and the things that used to move an anchor and now must not.

	"""

	def test_renaming_a_linked_target_moves_base_and_delta_together(self):
		"""A Page rather than a Report, because a Report cannot be renamed."""
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
		"""What makes the repair reach it: the stored row carries the real columns, so the rename's
		`UPDATE ... SET link_to` finds it like any other Dynamic Link.
		"""
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
		"""The price of storing a real Dynamic Link: a link blocks a delete unless the model says this
		kind of link is not a reference. A sidebar item is not: it is a way in, and a dangling one is
		already skipped on read, so a user hiding something in their own sidebar must not be able to
		stop an admin deleting it.

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
		"""The other half of the same price: a stored link is validated on save, so a row left naming
		a deleted item would turn every later write to that layer into a link error, whether renaming
		the sidebar or adding a workspace's link.

		It stops applying, which is what an item the app has deleted has always done. It does not stop
		the layer being written.

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

			self.assertEqual(self.resolved(module).label, "Renamed Module")

	def test_inserting_an_item_does_not_re_anchor_other_deltas(self):
		"""The ordinal is gone, and with it the thing that made an insertion move every anchor below
		it.
		"""
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
		"""An unlinked row has nothing to repair, so it keeps a stored key, hashed from its type and
		label, both of which a recomputation reproduces exactly.
		"""
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
	"""`Workspace Manager`, not System Manager: the role named for curating navigation, granted to
	nobody by default.
	"""

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
		"""The endpoint is not the only door: without a document-level gate a plain user could write
		the site layer straight from the doctype.
		"""
		self.as_user()
		doc = frappe.get_doc({"doctype": "Custom Sidebar", "module": MODULE, "user": ""})

		with self.assertRaises(frappe.PermissionError):
			doc.insert()

	def test_a_desk_user_may_write_their_own_layer_from_the_form(self):
		self.as_user()
		doc = frappe.get_doc(
			{"doctype": "Custom Sidebar", "module": MODULE, "user": frappe.session.user}
		).insert()

		self.assertTrue(frappe.db.exists("Custom Sidebar", doc.name))

	def test_a_workspace_manager_can_write_the_site_layer(self):
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		frappe.set_user(MANAGER)
		save_site_sidebar(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		self.as_user()
		self.assertNotIn(target["key"], self.keys())

	def test_one_users_preferences_stay_out_of_another_users_reads(self):
		"""Nobody but a Workspace Manager reads another user's arrangement. The manager reads
		everything, and the list view's default filter is what keeps a site audit, and the export that
		follows it, to the site layer alone.
		"""
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([]))

		frappe.set_user(MANAGER)
		save_site_sidebar(MODULE, json.dumps([]))
		self.assertEqual(
			{row.user for row in frappe.get_list("Custom Sidebar", fields=["user"])},
			{"", USER},
		)

		self.as_user()
		self.assertEqual(
			{row.user for row in frappe.get_list("Custom Sidebar", fields=["user"])},
			{USER},
		)


class TestUserRowsAreTheUsers(CustomizationTestCase):
	def test_deleting_a_user_takes_their_arrangement_with_them(self):
		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([]))
		frappe.set_user("Administrator")
		save_site_sidebar(MODULE, json.dumps([]))

		self.assertTrue(frappe.db.exists("Custom Sidebar", {"user": USER}))

		frappe.delete_doc("User", USER, force=True, ignore_permissions=True)

		self.assertFalse(frappe.db.exists("Custom Sidebar", {"user": USER}))
		# the site layer is nobody's personal preference
		self.assertTrue(frappe.db.exists("Custom Sidebar", {"user": ""}))


class TestOnlyTheOwnersLayerHoldsAPrivatePage(CustomizationTestCase):
	"""A row naming a private page belongs in its owner's own layer, and nowhere else.

	There it is what makes the page's place a stored fact, so the owner can arrange it and hide it
	from a module's sidebar. In the site's layer it would fill the document the whole site shares
	with one row per private page of whoever last curated it, and an admin tidying up would find
	other people's pages in it.

	A page with no row of its own still reaches its owner, derived on read from the workspace, so
	a row dropped here loses nothing.
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

	def test_the_owners_own_layer_keeps_their_own_page(self):
		"""Their own page in their own layer is the one place such a row belongs."""
		private = self.make_workspace("Test Own Layer Private Page", public=0, for_user=USER)

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([self.row_for(private)]))

		self.assertEqual(self.stored_links(USER), [private.name])

	def test_a_users_layer_drops_somebody_elses_page(self):
		"""A row about a page its reader cannot open says nothing, whichever user's layer it is in."""
		private = self.make_workspace("Test Other Owner Private Page", public=0, for_user="Administrator")

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([self.row_for(private)]))

		self.assertEqual(self.stored_links(USER), [])

	def test_a_page_with_no_owner_may_be_stored_anywhere(self):
		"""`public = 0` with no `for_user` is a page `get_workspaces` shows to everybody, so it is
		shared in all but the column and a layer may hold it.

		It is the case the filter used to answer by accident: `!=` is wrapped in `ifnull(col, '')`,
		so the site layer, whose `user` is the empty string, kept an unowned page and dropped every
		owned one, which is the rule upside down on one side.
		"""
		unowned = self.make_workspace("Test Unowned Private Page", public=0)

		save_site_sidebar(MODULE, json.dumps([self.row_for(unowned)]))
		self.assertEqual(self.stored_links(), [unowned.name])

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([self.row_for(unowned)]))
		self.assertEqual(self.stored_links(USER), [unowned.name])

	def test_a_page_that_turns_private_takes_its_stored_row_out_on_the_next_save(self):
		"""What retires the rows a site stored before the derivation existed: every write runs the
		rule, so the next save of that layer removes them.
		"""
		workspace = self.make_workspace("Test Turned Private Page", public=1)
		save_site_sidebar(MODULE, json.dumps([self.row_for(workspace)]))
		self.assertEqual(self.stored_links(), [workspace.name])

		frappe.db.set_value("Workspace", workspace.name, {"public": 0, "for_user": USER})
		save_site_sidebar(MODULE, label="Renamed")

		self.assertEqual(self.stored_links(), [])


class TestTheModelSaysWhatItMeans(IntegrationTestCase):
	def test_the_old_tables_are_gone(self):
		"""One child table serves base, site and user, so the preference table and the separate
		added-items table have nothing left to hold.

		It is asserted on the app rather than the site: a doctype is gone when it stops being shipped,
		and `remove_orphan_doctypes` drops the row on the next migrate.

		"""
		import os

		self.assertFalse(
			os.path.exists(frappe.get_app_path("frappe", "desk", "doctype", "sidebar_item_preference"))
		)

		fieldnames = {df.fieldname for df in frappe.get_meta("Custom Sidebar").fields}
		self.assertIn("sidebar_items", fieldnames)
		self.assertNotIn("items", fieldnames)
		self.assertNotIn("added_items", fieldnames)

	def test_the_child_carries_both_flags(self):
		fieldnames = {df.fieldname for df in frappe.get_meta("Sidebar Item").fields}

		self.assertIn("hidden", fieldnames)
		self.assertIn("added", fieldnames)

	def test_the_doctype_records_why_it_holds_user_rows(self):
		"""The `Custom *` prefix means site-owned everywhere else in the repo. The next reader has to
		find out why this one is different before they "fix" it.
		"""
		description = frappe.db.get_value("DocType", "Custom Sidebar", "description") or ""

		self.assertIn("user", description)
		self.assertIn("site layer", description)


class TestCustomizationTarget(CustomizationTestCase):
	"""What a customization has to be of.

	Not a `Sidebar`: most modules have no document at all, their base being computed from their
	contents, and those are exactly as customizable as a shipped one. The module is the thing that
	has to exist.

	"""

	def test_a_module_with_no_sidebar_document_can_be_customized(self):
		module = "Test Customizable Computed Module"
		self.addCleanup(self.wipe, module)

		with sidebarless_module(module):
			doomed = make_report(module, "Test Customizable Report")
			# A second one, so hiding the first leaves something navigable behind. A module with
			# nothing left but its section headers is dropped from the payload entirely.
			survivor = make_report(module, "Test Surviving Customizable Report")

			# by link, not by position: a computed base leads with a section header
			def key_for(name):
				return next(i["key"] for i in self.items(module) if i["link_to"] == name)

			save_sidebar_customization(module, json.dumps([{"key": key_for(doomed.name), "hidden": 1}]))

			links = [i["link_to"] for i in self.items(module)]
			self.assertNotIn(doomed.name, links)
			self.assertIn(survivor.name, links)

	def test_deleting_the_module_takes_its_customizations_with_it(self):
		"""A layer is anchored to a module, so it goes when the module does, the same rule the sidebar
		document follows.

		It has to be stated now. A Link used to refuse the delete on the row's behalf, and navigation
		links no longer do: `ignore_links_on_delete` covers this doctype so that nobody's sidebar
		preference can stop a document being deleted. Refusing was never right for a module either, and
		deleting one now cleans up after itself.

		"""
		module = "Test Deleted Module With Customization"
		with no_developer_mode():
			frappe.get_doc({"doctype": "Module Def", "module_name": module, "app_name": "frappe"}).insert()

		save_site_sidebar(module, json.dumps([]))
		self.assertTrue(frappe.db.exists("Custom Sidebar", {"module": module}))

		with no_developer_mode():
			frappe.delete_doc("Module Def", module)

		self.assertFalse(frappe.db.exists("Custom Sidebar", {"module": module}))

	def test_a_module_that_does_not_exist_cannot_be_customized(self):
		"""Asserted on the message, because the child table's own Link validation would raise a
		`ValidationError` too, and that one fires only after the write has been assembled.
		"""
		with self.assertRaises(frappe.ValidationError) as caught:
			save_sidebar_customization("Test No Such Module", json.dumps([]))

		self.assertIn("is not a module", str(caught.exception))


class TestWhatTheEditorOpensOn(CustomizationTestCase):
	"""The read the editor opens a layer on.

	It is neither of the two answers that already existed. The boot payload is the resolution for the
	user and drops a hidden item, which an editor has to be able to bring back, and a layer's stored
	rows are a delta, while this editor saves the whole arrangement.

	"""

	def setUp(self):
		super().setUp()
		make_user(MANAGER, ["Desk User", "Workspace Manager"])

	def tearDown(self):
		super().tearDown()
		frappe.delete_doc("User", MANAGER, force=True, ignore_missing=True)

	def read(self, layer: str, module: str = MODULE):
		endpoint = get_user_sidebar_layer if layer == "user" else get_site_sidebar_layer
		return endpoint(module)

	def arrange(self, layer: str, on_the_sidebar: list[str], module: str = MODULE):
		"""The save the editor makes: the whole arrangement on screen, in one order, each entry
		carrying whether it is hidden. Each entry goes back as it came, which is the client contract
		`drop_inherited_values` is written against.
		"""
		shown = {item["key"]: item for item in self.read(layer, module)}
		return [{**shown[key], "hidden": 0} for key in on_the_sidebar] + [
			{**item, "hidden": 1} for key, item in shown.items() if key not in on_the_sidebar
		]

	def test_an_unarranged_layer_reads_as_the_layer_below(self):
		"""The starting-point rule. Nothing is stored at either layer, so each reads as the one below
		it: a user's own as the sidebar on their screen, the site's as what the apps ship, which is
		not narrowed to whoever is curating it. See the unfiltered read below.

		"""
		shipped = [item["key"] for item in self.base_items()]

		self.as_user()
		self.assertEqual(
			[item["key"] for item in self.read("user")],
			[item["key"] for item in self.items()],
		)

		frappe.set_user(MANAGER)
		self.assertEqual([item["key"] for item in self.read("site")], shipped)

	def test_a_hidden_item_is_kept_so_it_can_be_brought_back(self):
		"""The one thing the boot payload cannot say. The site hides an item, and the user's own layer
		opens with it still there, flagged, ready to be dragged back.
		"""
		target = next(i for i in self.base_items() if i["type"] != "Section Break")
		save_site_sidebar(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		self.as_user()
		self.assertNotIn(target["key"], self.keys())

		read = {item["key"]: item for item in self.read("user")}
		self.assertIn(target["key"], read)
		self.assertEqual(read[target["key"]]["hidden"], 1)

	def test_the_layer_being_edited_is_included(self):
		"""The arrangement as it stands, not the one below it. Otherwise reopening the editor would
		show none of the work the last save did.
		"""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		read = {item["key"]: item for item in self.read("user")}
		self.assertEqual(read[target["key"]]["hidden"], 1)

	def test_the_site_layer_reads_without_anybodys_own(self):
		"""A curator arranges for everyone, so what they open on is the site's arrangement, never the
		one their own preferences put on their screen.
		"""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		frappe.set_user(MANAGER)
		save_sidebar_customization(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		read = {item["key"]: item for item in self.read("site")}
		self.assertEqual(read[target["key"]]["hidden"], 0)

	def test_only_this_layers_own_added_rows_read_as_added(self):
		"""An item a layer below added is a reference from here. Read back as added, one save would
		copy its body into this layer and freeze what the layer below still owns.
		"""
		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "Test Editor Added Page",
				"label": "Test Editor Added Page",
				"module": MODULE,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", workspace.name, force=True, ignore_missing=True)

		row = {
			"added": 1,
			"type": "Link",
			"link_type": "Workspace",
			"link_to": workspace.name,
			"label": workspace.title,
		}
		save_site_sidebar(MODULE, json.dumps([*self.base_items(), row]))

		frappe.set_user(MANAGER)
		site = {item["key"]: item for item in self.read("site")}
		self.assertEqual(site[item_key(row)]["added"], 1)

		self.as_user()
		mine = {item["key"]: item for item in self.read("user")}
		self.assertEqual(mine[item_key(row)]["added"], 0)

	def test_saving_the_read_straight_back_says_nothing(self):
		"""The round trip the editor makes on every Save. Sending back what it was given, untouched,
		must leave the resolution as it was and must store no override.
		"""
		before = self.keys()

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps(self.read("user")))

		self.assertEqual(self.keys(), before)
		layer = get_customization(MODULE, USER)
		self.assertTrue(all(not row.label and not row.icon for row in layer.sidebar_items))

	def test_bringing_an_item_back_does_not_freeze_its_label(self):
		"""The read hands out a hidden item with the label it inherits. A row un-hiding it names an
		item that really exists, so that label is still inheritance. Storing it would stop the site's
		next relabel reaching this user.
		"""
		target = next(i for i in self.base_items() if i["type"] != "Section Break")
		save_site_sidebar(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		self.as_user()
		save_sidebar_customization(
			MODULE,
			json.dumps([{**item, "hidden": 0} for item in self.read("user")]),
		)

		self.assertIn(target["key"], self.keys())
		layer = get_customization(MODULE, USER)
		self.assertTrue(all(not row.label and not row.icon for row in layer.sidebar_items))

	def test_an_added_item_survives_the_editors_round_trip(self):
		"""The editor sends the whole arrangement back, added rows included. An added row is the item
		rather than a reference to one, so losing its body loses the entry.
		"""
		added = {
			"added": 1,
			"type": "Link",
			"link_type": "URL",
			"url": "https://example.com/handbook",
			"label": "Handbook",
			"icon": "book",
		}

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([*self.read("user"), added]))

		# it is on the sidebar, and reads back as this layer's own
		entry = next(i for i in self.read("user") if i["key"] == item_key(added))
		self.assertEqual((entry["added"], entry["label"], entry["icon"]), (1, "Handbook", "book"))

		# ... and a save that merely echoes what was read keeps it, body and all
		save_sidebar_customization(MODULE, json.dumps(self.read("user")))
		kept = next(i for i in self.items() if i["key"] == item_key(added))
		self.assertEqual(kept["url"], "https://example.com/handbook")

	def test_the_site_layer_is_read_unfiltered_so_a_save_cannot_drop_what_it_hid(self):
		"""Permission is a fact about each user, applied to what they boot. A curator given their own
		filtered screen would write the whole arrangement back without it, silently deleting the site's
		intent for everything they personally cannot open.
		"""
		everything = {i["key"] for i in self.base_items()}

		frappe.set_user(MANAGER)
		mine = {i["key"] for i in self.read("user")}
		self.assertLess(mine, everything, "sanity: this curator cannot see all of this module")

		self.assertEqual({i["key"] for i in self.read("site")}, everything)

	def test_the_site_layer_read_needs_the_shared_curation_right(self):
		"""The switch is absent for a user without it, and the endpoint refuses anyway."""
		self.as_user()
		self.assertNotIn("Workspace Manager", frappe.get_roles())

		with self.assertRaises(frappe.PermissionError):
			get_site_sidebar_layer(MODULE)

	def test_a_module_that_does_not_exist_cannot_be_opened(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			get_user_sidebar_layer("Test No Such Module")

		self.assertIn("is not a module", str(caught.exception))

	def test_the_editor_round_trips_a_reorder_a_hide_and_a_relabel(self):
		"""One save carrying all three things the editor can do, in the shape it sends them."""
		items = self.base_items()
		dropped, renamed = [i for i in items if i["type"] != "Section Break"][:2]
		keys = [i["key"] for i in items]
		kept = [key for key in reversed(keys) if key != dropped["key"]]

		self.as_user()
		rows = self.arrange("user", kept)
		for row in rows:
			if row["key"] == renamed["key"]:
				row["label"] = "Mine"
		save_sidebar_customization(MODULE, json.dumps(rows))

		resolved = self.items()
		self.assertEqual([i["key"] for i in resolved], kept)
		self.assertEqual(next(i for i in resolved if i["key"] == renamed["key"])["label"], "Mine")

		# ... and the reorder said nothing about anything but the one label it meant
		layer = get_customization(MODULE, USER)
		self.assertEqual([row.label for row in layer.sidebar_items if row.label], ["Mine"])

	def test_a_layer_can_add_a_section_and_put_an_entry_in_it(self):
		"""The other kind of row a layer may add: one that leads nowhere and names the entries under
		it. It is stored without a key, because a row that leads nowhere is named by a hash of its
		type and label, and the model computes that, so the editor's own version of the identity never
		becomes a second name for the same section.
		"""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(
			MODULE,
			json.dumps(
				[
					{"added": 1, "type": "Section Break", "label": "Mine", "key": None},
					{**target, "child": 1, "hidden": 0},
				]
			),
		)

		resolved = self.items()
		section = next(i for i in resolved if i["label"] == "Mine")
		self.assertEqual(section["type"], "Section Break")
		self.assertEqual(section["key"], unlinked_key({"type": "Section Break", "label": "Mine"}))

		# ... and the entry dropped under it is a member of it
		member = next(i for i in resolved if i["key"] == target["key"])
		self.assertEqual(member["child"], 1)
		self.assertEqual(resolved.index(member), resolved.index(section) + 1)

	def test_an_entry_can_be_put_into_a_section_and_taken_back_out(self):
		"""Where an entry is dropped decides which section it is in, so the arrangement states
		membership for every row it holds, including a row that has just stopped being a member, which
		is the half a `Check` cannot express as an override. Both directions are tested together
		because only the second is new: claiming a membership would work by accident, while un-claiming
		one needs the value stored rather than overridden.
		"""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")
		keys = [i["key"] for i in items]

		def membership():
			return next(i for i in self.items() if i["key"] == target["key"])["child"]

		def drag(child):
			rows = self.arrange("user", keys)
			for row in rows:
				if row["key"] == target["key"]:
					row["child"] = child
			save_sidebar_customization(MODULE, json.dumps(rows))

		self.as_user()

		drag(1)
		self.assertEqual(membership(), 1)

		# ... and dragged back out from under it, which the layer has to be able to say
		drag(0)
		self.assertEqual(membership(), 0)

	def test_a_site_can_be_put_back_to_what_the_apps_ship(self):
		"""The other reset. `reset_user_sidebar` has its own test; this one had no caller at all until
		the editor's Reset button.
		"""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")
		keys = [i["key"] for i in items]

		save_site_sidebar(MODULE, json.dumps(self.arrange("site", [k for k in keys if k != target["key"]])))
		self.assertNotIn(target["key"], self.keys())

		reset_site_sidebar(MODULE)

		self.assertEqual(self.keys(), keys)
		self.assertIsNone(get_customization(MODULE, None))


class TestResetToStandard(CustomizationTestCase):
	"""The third reset: not one layer down, but back to the module's `Sidebar`.

	The other two each drop one layer and let the next show through. This one promises the module is
	using what its app ships, which is only true if nothing is laid over it for anybody.

	"""

	def setUp(self):
		super().setUp()
		make_user(MANAGER, ["Desk User", "Workspace Manager"])

	def tearDown(self):
		super().tearDown()
		frappe.delete_doc("User", MANAGER, force=True, ignore_missing=True)

	def arrange_every_layer(self):
		"""A site layer and two people's own, all hiding something."""
		target = next(i for i in self.base_items() if i["type"] != "Section Break")
		row = json.dumps([{"key": target["key"], "hidden": 1}])

		save_site_sidebar(MODULE, row)
		for user in (USER, MANAGER):
			frappe.set_user(user)
			save_sidebar_customization(MODULE, row)
		frappe.set_user("Administrator")

		return target

	def test_it_takes_every_layer_off_the_module(self):
		target = self.arrange_every_layer()
		self.assertEqual(
			{
				row.user
				for row in frappe.get_all("Custom Sidebar", filters={"module": MODULE}, fields=["user"])
			},
			{"", USER, MANAGER},
		)

		reset_to_standard(MODULE)

		self.assertEqual(frappe.get_all("Custom Sidebar", filters={"module": MODULE}), [])
		# ... and everybody is looking at the module's own sidebar again, not just the caller
		for user in (USER, MANAGER):
			frappe.set_user(user)
			self.assertIn(target["key"], self.keys())

	def test_it_leaves_other_modules_alone(self):
		"""Anchored to one module, like every other write here."""
		self.arrange_every_layer()
		with sidebarless_module("Test Untouched By Reset") as other:
			self.addCleanup(self.wipe, other)
			make_report(other, "Test Untouched Report")
			save_site_sidebar(other, json.dumps([]))

			reset_to_standard(MODULE)

			self.assertTrue(frappe.db.exists("Custom Sidebar", {"module": other}))

	def test_it_needs_the_shared_curation_right(self):
		"""It discards other users' arrangements, so it is behind the right to act for everyone, the
		same gate `reset_site_sidebar` carries.
		"""
		self.arrange_every_layer()

		self.as_user()
		self.assertNotIn("Workspace Manager", frappe.get_roles())
		with self.assertRaises(frappe.PermissionError):
			reset_to_standard(MODULE)

		frappe.set_user("Administrator")
		self.assertTrue(frappe.db.exists("Custom Sidebar", {"module": MODULE}))

	def test_a_module_that_does_not_exist_is_refused(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			reset_to_standard("Test No Such Module")

		self.assertIn("is not a module", str(caught.exception))


class TestAnAddedItemIsStillPermissionChecked(CustomizationTestCase):
	"""A row that adds an item brings one the base never held, so the filter that runs before the
	layers never saw it.

	Every other row names an item already in the list, which is what makes it true for them that a
	layer can never widen what someone may reach. An added row has to be checked on its own, or a
	curator adding a link for everyone hands it to users who may not follow it.

	"""

	def setUp(self):
		super().setUp()
		make_user(MANAGER, ["Desk User", "Workspace Manager"])

	def tearDown(self):
		super().tearDown()
		frappe.delete_doc("User", MANAGER, force=True, ignore_missing=True)

	def add_to_site_layer(self, **item):
		save_site_sidebar(MODULE, json.dumps([*self.base_items(), {"added": 1, "type": "Link", **item}]))

	def test_an_added_item_the_reader_may_not_open_is_dropped(self):
		self.add_to_site_layer(link_type="DocType", link_to="Custom Field", label="Custom Field")

		frappe.set_user(MANAGER)
		self.assertNotIn("Custom Field", [item["link_to"] for item in self.items()])

	def test_an_added_item_the_reader_may_open_is_kept(self):
		"""The other half, so the check cannot pass by dropping everything."""
		self.add_to_site_layer(link_type="DocType", link_to="Custom Field", label="Custom Field")

		self.as_user()
		self.assertIn("Custom Field", [item["link_to"] for item in self.items()])

	def test_an_added_url_is_nobody_s_to_block(self):
		"""A URL leads out of the site, so there is no permission on it to check, which is the answer
		`is_item_allowed` has always given for one.
		"""
		self.add_to_site_layer(link_type="URL", url="https://example.com", label="Somewhere Else")

		frappe.set_user(MANAGER)
		self.assertIn("https://example.com", [item["url"] for item in self.items()])


class TestPageRouteIsPartOfTheIdentity(CustomizationTestCase):
	"""Two items linking one page and naming different routes are two items to a layer.

	erpnext's Accounts sidebar holds two of them, both linking `insights-dashboard`. Sharing an
	identity dropped the second from the boot payload, and would make a layer's row about one of
	them apply to the other.
	"""

	MODULE = "Test Page Route Module"

	def routed_module(self):
		"""A module whose sidebar is two routes into one page."""
		module = sidebarless_module(self.MODULE)
		module.__enter__()
		self.addCleanup(module.__exit__, None, None, None)
		self.addCleanup(self.wipe, self.MODULE)
		page = make_page(self.MODULE, "test-route-page")
		self.addCleanup(delete_page, page.name)

		doc = frappe.new_doc("Sidebar")
		doc.module = self.MODULE
		for route in ("accounts", "payments"):
			doc.append(
				"items",
				{
					"type": "Link",
					"link_type": "Page",
					"link_to": page.name,
					"label": route.title(),
					"route": route,
				},
			)
		with developer_mode():
			doc.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Sidebar", doc.name, force=True, ignore_permissions=True)

	def routes(self):
		return [item.get("route") for item in self.items(self.MODULE)]

	def test_an_arrangement_keeps_both(self):
		"""A saved arrangement names each item by its key, so a shared key would fold the two
		into one row and lose the other on the next resolution."""
		self.routed_module()

		self.as_user()
		items = self.items(self.MODULE)
		self.assertEqual(len({item["key"] for item in items}), 2, "sanity: two identities")

		save_sidebar_customization(self.MODULE, json.dumps(list(reversed(items))))

		self.assertEqual(self.routes(), ["payments", "accounts"])

	def test_hiding_one_route_leaves_the_other(self):
		self.routed_module()

		self.as_user()
		payments = next(i for i in self.items(self.MODULE) if i["route"] == "payments")
		save_sidebar_customization(self.MODULE, json.dumps([{**payments, "hidden": 1}]))

		self.assertEqual(self.routes(), ["accounts"])


class TestAPrivatePageWritesItsRows(CustomizationTestCase):
	"""Making a private page says, in stored rows, which sidebars list it.

	It used to say nothing: the page was appended to its owner's sidebars derived on read, so
	nothing stored held it and the owner could neither arrange it nor hide it from the module it
	was filed under. Two rows now do: one in their `Private` layer, which is the page's home, and
	one in the layer of the module it is a guest in.
	"""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		ensure_module(PRIVATE_MODULE)
		self.addCleanup(self.wipe, PRIVATE_MODULE)

	def make_page(self, title, module=MODULE, for_user=USER, public=0, ignore_permissions=True):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": f"{title}-{for_user}" if for_user else title,
				"module": module,
				"public": public,
				"for_user": for_user or "",
				"content": "[]",
			}
		).insert(ignore_permissions=ignore_permissions)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		return doc

	def rows(self, module, user):
		layer = get_customization(module, user)
		return [(row.link_to, row.label) for row in layer.sidebar_items] if layer else []

	def test_a_new_page_lands_in_the_private_layer_and_its_modules(self):
		page = self.make_page("Test Rows New Page")

		self.assertEqual(self.rows(PRIVATE_MODULE, USER), [(page.name, page.title)])
		self.assertEqual(self.rows(MODULE, USER), [(page.name, page.title)])

	def test_a_page_of_the_private_module_gets_one_row(self):
		"""It is only at home. There is no second sidebar for it to be a guest in."""
		page = self.make_page("Test Rows Private Module Page", module=PRIVATE_MODULE)

		self.assertEqual(self.rows(PRIVATE_MODULE, USER), [(page.name, page.title)])

	def test_nothing_is_written_to_the_site_layer(self):
		self.make_page("Test Rows Site Layer Page")

		self.assertEqual(self.rows(MODULE, None), [])
		self.assertEqual(self.rows(PRIVATE_MODULE, None), [])

	def test_a_shared_page_still_goes_to_the_site_layer(self):
		"""The other half of the rule. A shared page's row is written by the path that created it,
		rather than on insert, because that path knows whether it wanted one at all: the page a new
		module opens on is listed by the module's own sidebar already.
		"""
		page = self.make_page("Test Rows Shared Page", for_user="", public=1)
		self.assertEqual(self.rows(MODULE, None), [], "nothing on insert")

		add_to_sidebar(page)

		self.assertEqual(self.rows(MODULE, USER), [])
		self.assertIn(page.name, [link for link, _label in self.rows(MODULE, None)])

	def test_moving_it_to_another_module_moves_its_row(self):
		page = self.make_page("Test Rows Moving Page")
		page.module = "Contacts"
		page.save(ignore_permissions=True)
		self.addCleanup(self.wipe, "Contacts")

		self.assertEqual(self.rows(MODULE, USER), [])
		self.assertEqual(self.rows("Contacts", USER), [(page.name, page.title)])
		self.assertEqual(self.rows(PRIVATE_MODULE, USER), [(page.name, page.title)], "still at home")

	def test_a_page_turning_private_leaves_no_row_behind(self):
		"""It was shared a moment ago, so the site's layer holds a row for it and so does everyone
		who had arranged the module that listed it. None of them may keep a row naming a page they
		can no longer open, so the removal covers every layer and not only the new owner's.
		"""
		page = self.make_page("Test Rows Turning Private", for_user="", public=1)
		add_to_sidebar(page)
		self.held_by(page, 2)
		self.assertTrue(self.rows(MODULE, None), "sanity: the site layer holds it while shared")

		page.public = 0
		page.for_user = USER
		page.label = f"{page.title}-{USER}"
		page.save(ignore_permissions=True)

		everywhere = frappe.get_all(
			"Sidebar Item",
			filters={"parenttype": "Custom Sidebar", "link_to": page.name},
			fields=["parent"],
		)
		holders = {
			row.parent: frappe.db.get_value("Custom Sidebar", row.parent, "user") for row in everywhere
		}
		self.assertEqual(sorted(set(holders.values())), [USER], "only the new owner's layers name it now")

	def test_renaming_it_renames_its_rows(self):
		page = self.make_page("Test Rows Renaming Page")
		page.title = "Test Rows Renamed Page"
		page.save(ignore_permissions=True)

		self.assertEqual(self.rows(PRIVATE_MODULE, USER), [(page.name, "Test Rows Renamed Page")])

	def held_by(self, page, holders: int):
		"""Put a row naming `page` in `holders` different users' layers."""
		for i in range(holders):
			email = f"test-sidebar-holder-{i}@example.com"
			make_user(email, ["Desk User"])
			self.addCleanup(frappe.delete_doc, "User", email, force=True, ignore_missing=True)
			layer = frappe.new_doc("Custom Sidebar")
			layer.module = MODULE
			layer.user = email
			layer.append(
				"sidebar_items",
				{
					"added": 1,
					"type": "Link",
					"link_type": "Workspace",
					"link_to": page.name,
					"label": page.title,
				},
			)
			layer.insert(ignore_permissions=True)

	def test_deleting_a_page_costs_the_same_however_many_layers_hold_it(self):
		"""A shared page is referenced by everyone who has arranged the module that lists it, so a
		document read and a document write per layer made deleting one cost a round trip per user of
		the site. The statements are set-based now, so the cost is the same for one layer and eight.

		The number itself is not the claim, which is why the same bound is asserted twice rather
		than written down once: what must hold is that it does not grow.
		"""
		one = self.make_page("Test Rows Held Once", for_user="", public=1)
		self.held_by(one, 1)
		with self.assertQueryCount(6):
			remove_workspace_rows(one.name)

		many = self.make_page("Test Rows Held Widely", for_user="", public=1)
		self.held_by(many, 8)
		with self.assertQueryCount(6):
			remove_workspace_rows(many.name)

		self.assertEqual(
			frappe.get_all(
				"Sidebar Item",
				filters={"parenttype": "Custom Sidebar", "link_to": ["in", [one.name, many.name]]},
				pluck="name",
			),
			[],
		)

	def test_it_can_be_deleted_on_a_developer_site(self):
		"""A page nobody exported has no folder to remove, and asking for one is not free: the path
		of a module the site owns cannot be resolved unless that module names a package. Deleting a
		private page used to fail with "Package must be set for custom Module Private".
		"""
		page = self.make_page("Test Rows Developer Delete Page", module=PRIVATE_MODULE)

		with developer_mode():
			frappe.delete_doc("Workspace", page.name, force=True)

		self.assertFalse(frappe.db.exists("Workspace", page.name))

	def test_nobody_can_make_a_page_for_somebody_else(self):
		"""A private page belongs to one person, and making one writes rows into that person's own
		layer. Left unchecked, anyone holding `Desk User` could insert a Workspace naming somebody
		else in `for_user` through the generic API and put a row in their sidebar.

		The endpoints said so already (`new_page`, `update_page`); the model says it now, because a
		document API call reaches neither.
		"""
		make_user(OTHER, ["Desk User"])
		self.addCleanup(frappe.delete_doc, "User", OTHER, force=True, ignore_missing=True)

		self.as_user()
		with self.assertRaises(frappe.PermissionError):
			# Through the permission system, as the document API goes: `ignore_permissions` is
			# what a trusted caller passes, and the point here is an untrusted one.
			self.make_page("Test Rows Somebody Elses Page", for_user=OTHER, ignore_permissions=False)

		frappe.set_user("Administrator")
		self.assertEqual(self.rows(PRIVATE_MODULE, OTHER), [])

	def test_a_workspace_manager_may_make_one_for_somebody_else(self):
		"""Which is what the manager dialog does, and what the endpoints have always allowed."""
		make_user(OTHER, ["Desk User"])
		self.addCleanup(frappe.delete_doc, "User", OTHER, force=True, ignore_missing=True)
		make_user(MANAGER, ["System Manager", "Workspace Manager"])
		self.addCleanup(frappe.delete_doc, "User", MANAGER, force=True, ignore_missing=True)

		frappe.set_user(MANAGER)
		page = self.make_page("Test Rows Managed Page", for_user=OTHER, ignore_permissions=False)

		frappe.set_user("Administrator")
		self.assertEqual(self.rows(PRIVATE_MODULE, OTHER), [(page.name, page.title)])

	def test_deleting_it_takes_its_rows_out(self):
		page = self.make_page("Test Rows Deleting Page")
		frappe.delete_doc("Workspace", page.name, force=True)

		self.assertEqual(self.rows(PRIVATE_MODULE, USER), [])
		self.assertEqual(self.rows(MODULE, USER), [])

		# And the layers the page's own creation made, which now say nothing at all.
		self.assertIsNone(get_customization(PRIVATE_MODULE, USER))
		self.assertIsNone(get_customization(MODULE, USER))

	def test_hiding_it_in_a_modules_sidebar_sticks(self):
		"""The page is a guest there, so it may be sent away. Before the layers said which keys they
		hid, the derived append read the gap as a page nothing named and put it straight back.
		"""
		page = self.make_page("Test Rows Hiding Page")

		self.as_user()
		rows = get_user_sidebar_layer(MODULE)
		save_sidebar_customization(
			MODULE,
			json.dumps([{**row, "hidden": 1 if row["link_to"] == page.name else 0} for row in rows]),
		)

		self.assertNotIn(page.name, [item.get("link_to") for item in self.items(MODULE)])

	def test_it_cannot_be_hidden_from_its_own_shell(self):
		"""The Private shell is where every page its owner made appears, so a row left out comes
		back derived from the page itself."""
		page = self.make_page("Test Rows Pinned Page", module=PRIVATE_MODULE)

		self.as_user()
		save_sidebar_customization(PRIVATE_MODULE, json.dumps([]))

		self.assertIn(page.name, [item.get("link_to") for item in self.items(PRIVATE_MODULE)])
