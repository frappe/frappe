# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.doctype.custom_sidebar.custom_sidebar import (
	get_customization,
	get_layers_for,
	get_site_sidebar_layer,
	get_user_sidebar_layer,
	reset_site_sidebar,
	reset_to_standard,
	reset_user_sidebar,
	save_sidebar_customization,
	save_site_sidebar,
)
from frappe.desk.doctype.sidebar.sidebar import item_key, resolve_sidebar, unlinked_key
from frappe.desk.doctype.sidebar.test_sidebar import (
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
		for name in frappe.get_all("Custom Sidebar", filters={"module": module}, pluck="name"):
			frappe.delete_doc("Custom Sidebar", name, force=True, ignore_permissions=True)
		frappe.clear_cache(user=USER)

	def resolved(self, module: str = MODULE):
		"""What `module` resolves to for the session user -- the seam every layer lands in."""
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
		"""The cost-control story, stated as the thing that is actually true: which layers apply
		is a question about the reader, so it is asked once per resolution rather than once per
		module. Asserted against a real set of modules, because the failure this guards against
		is a lookup that quietly moved back inside the loop."""
		from frappe.desk.doctype.sidebar.sidebar import get_navigable_modules

		modules = get_navigable_modules()
		self.assertGreater(len(modules), 1, "sanity: more than one module to batch")

		with self.assertQueryCount(1):
			get_layers_for(frappe.session.user, modules)

	def test_a_layer_is_found_however_the_site_row_spells_unset(self):
		"""A blank Link stores as `''` or as NULL depending on how the row was written, and both
		spellings are the site layer."""
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

		self.assertIsNone(self.resolved())

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
		sidebar = self.resolved()
		self.assertEqual(sidebar.label, "Site Label")
		self.assertEqual(sidebar.header_icon, "star")

		save_sidebar_customization(MODULE, label="My Label")
		self.assertEqual(self.resolved().label, "My Label")


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

	A delta row and the base row it names are both `Sidebar Item` rows carrying a
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

			self.assertEqual(self.resolved(module).label, "Renamed Module")

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
		"""Nobody but a Workspace Manager reads anyone else's arrangement. The manager reads
		everything -- and the list view's default filter is what keeps a site audit, and the
		export that follows it, to the site layer alone."""
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
		"""The `Custom *` prefix means site-owned everywhere else in the repo. The next reader
		has to find out why this one is different before they "fix" it."""
		description = frappe.db.get_value("DocType", "Custom Sidebar", "description") or ""

		self.assertIn("user", description)
		self.assertIn("site layer", description)


class TestCustomizationTarget(CustomizationTestCase):
	"""What a customization has to be *of*.

	Not a `Sidebar`: most modules have no document at all, their base being computed
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
		self.assertTrue(frappe.db.exists("Custom Sidebar", {"module": module}))

		with no_developer_mode():
			frappe.delete_doc("Module Def", module)

		self.assertFalse(frappe.db.exists("Custom Sidebar", {"module": module}))

	def test_a_module_that_does_not_exist_cannot_be_customized(self):
		"""Asserted on the message, because the child table's own Link validation would raise
		a `ValidationError` too -- and that one fires only after the write has been assembled."""
		with self.assertRaises(frappe.ValidationError) as caught:
			save_sidebar_customization("Test No Such Module", json.dumps([]))

		self.assertIn("is not a module", str(caught.exception))


class TestWhatTheEditorOpensOn(CustomizationTestCase):
	"""The read the editor opens a layer on.

	It is neither of the two answers that already existed. The boot payload is the resolution
	for the reader and drops a hidden item, which an editor has to be able to bring back; a
	layer's stored rows are a delta, and this editor saves the whole arrangement.
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
		carrying whether it is hidden. Each entry goes back as it came, which is the client
		contract `drop_inherited_values` is written against."""
		shown = {item["key"]: item for item in self.read(layer, module)}
		return [{**shown[key], "hidden": 0} for key in on_the_sidebar] + [
			{**item, "hidden": 1} for key, item in shown.items() if key not in on_the_sidebar
		]

	def test_an_unarranged_layer_reads_as_the_layer_below(self):
		"""The starting point rule. Nothing is stored at either layer, so each reads as the one
		below it: a person's own as the sidebar on their screen, the site's as what the apps
		ship -- which is not narrowed to whoever is curating it, see the unfiltered read below.
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
		"""The one thing the boot payload cannot say. The site hides an item; the person's own
		layer opens on it still there, flagged, ready to be dragged back."""
		target = next(i for i in self.base_items() if i["type"] != "Section Break")
		save_site_sidebar(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		self.as_user()
		self.assertNotIn(target["key"], self.keys())

		read = {item["key"]: item for item in self.read("user")}
		self.assertIn(target["key"], read)
		self.assertEqual(read[target["key"]]["hidden"], 1)

	def test_the_layer_being_edited_is_included(self):
		"""The arrangement as it stands, not the one below it -- otherwise reopening the editor
		would show none of the work the last save did."""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		read = {item["key"]: item for item in self.read("user")}
		self.assertEqual(read[target["key"]]["hidden"], 1)

	def test_the_site_layer_reads_without_anybodys_own(self):
		"""A curator arranges for everyone, so what they open on is the site's arrangement --
		never the one their own preferences put on their screen."""
		items = self.base_items()
		target = next(i for i in items if i["type"] != "Section Break")

		frappe.set_user(MANAGER)
		save_sidebar_customization(MODULE, json.dumps([{"key": target["key"], "hidden": 1}]))

		read = {item["key"]: item for item in self.read("site")}
		self.assertEqual(read[target["key"]]["hidden"], 0)

	def test_only_this_layers_own_added_rows_read_as_added(self):
		"""An item a layer below added is a *reference* from here. Read back as added, one save
		would copy its body into this layer and freeze what the layer below still owns."""
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
		"""The round trip the editor makes on every Save. Sending back what it was handed,
		untouched, must leave the resolution exactly as it was -- and must store no opinion."""
		before = self.keys()

		self.as_user()
		save_sidebar_customization(MODULE, json.dumps(self.read("user")))

		self.assertEqual(self.keys(), before)
		layer = get_customization(MODULE, USER)
		self.assertTrue(all(not row.label and not row.icon for row in layer.sidebar_items))

	def test_bringing_an_item_back_does_not_freeze_its_label(self):
		"""The read hands out a hidden item with the label it inherits. A row un-hiding it is
		naming an item that is really there, so that label is still inheritance -- storing it
		would stop the site's next relabel ever reaching this person."""
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
		"""The editor sends the whole arrangement back, added rows included. An added row is the
		item rather than a reference to one, so losing its body loses the entry itself."""
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
		"""Who may see an item is a fact about the reader, applied to what each person boots. A
		curator handed their own filtered screen would write the whole arrangement back without
		it, quietly deleting the site's intent for everything they personally cannot open."""
		everything = {i["key"] for i in self.base_items()}

		frappe.set_user(MANAGER)
		mine = {i["key"] for i in self.read("user")}
		self.assertLess(mine, everything, "sanity: this curator cannot see all of this module")

		self.assertEqual({i["key"] for i in self.read("site")}, everything)

	def test_the_site_layer_read_needs_the_shared_curation_right(self):
		"""The switch is absent for a person without it, and the endpoint says so anyway."""
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
		"""The other kind of row a layer may add: one that leads nowhere and names the run under
		it. It is stored without a key, because a row that leads nowhere is named by a hash of
		its type and its label and the model is what works that out -- so the editor's own
		spelling of that identity never becomes a second name for the same section."""
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
		"""Where an entry is dropped is what says which section it is in, so the arrangement
		states membership for every row it holds -- including the row that has just stopped
		being a member, which is the half a `Check` cannot spell as an opinion. Both directions
		are tested in one go because only the second one is new: claiming a membership would
		work by accident, un-claiming one is what needs the value stored rather than opined."""
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
		"""The other reset. `reset_user_sidebar` has a test of its own; this one had no caller at
		all until the editor's Reset button."""
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

	The other two each drop one layer and let the next show through. This one promises the
	module is using what its app ships -- which is only true if nothing is laid over it, for
	anybody.
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
		"""It discards other people's arrangements, so it is behind the right to act for
		everyone -- the same gate `reset_site_sidebar` carries."""
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
	"""A row that *adds* an item brings one the base never held, so the filter that runs before
	the layers never saw it.

	Every other row names an item that is already in the list, which is what makes "a layer can
	never widen what somebody may reach" true for them. An added row has to be checked on its
	own, or a curator adding a link for everyone hands it to the people who may not follow it.
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
		"""A URL leads out of the site, so there is no permission on it to check -- the same
		answer `is_item_allowed` has always given one."""
		self.add_to_site_layer(link_type="URL", url="https://example.com", label="Somewhere Else")

		frappe.set_user(MANAGER)
		self.assertIn("https://example.com", [item["url"] for item in self.items()])
