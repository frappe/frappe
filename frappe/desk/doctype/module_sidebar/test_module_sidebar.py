# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from contextlib import contextmanager

import frappe
from frappe.desk.doctype.module_sidebar.module_sidebar import (
	COMPUTED_BASE_CACHE_KEY,
	MODULE_CONTENT_DOCTYPES,
	SYSTEM_WRITE_FLAGS,
	build_all,
	build_module_sidebar,
	clear_computed_base_cache,
	get_computed_base,
	get_module_sidebar_sources,
	item_key,
	mark_as_standard,
	pick_primary,
	ship_dock_order,
	unmark_as_standard,
)
from frappe.tests import IntegrationTestCase

MODULE = "Test Sidebar Module"


@contextmanager
def no_developer_mode():
	"""Create/delete a Module Def without touching the app on disk.

	In developer_mode a Module Def writes itself into the app's modules.txt and creates a
	folder on insert, but only undoes that on `after_commit` -- which a rolled-back test
	never reaches, so the fixture would leak into the working tree.
	"""
	original = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 0
	try:
		yield
	finally:
		frappe.conf.developer_mode = original


@contextmanager
def developer_mode():
	"""Exporting to files is gated on developer_mode; the test site may not have it on."""
	original = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 1
	try:
		yield
	finally:
		frappe.conf.developer_mode = original


@contextmanager
def system_write(flag="in_import"):
	"""The system placing app content on a site, rather than a person authoring it.

	Each of these flags is set by a real route -- an import, a fixture sync, a migrate, an app
	install, a patch -- and each clears the developer-mode gate, since an app that ships a
	sidebar has to be installable on a customer site.
	"""
	original = frappe.flags.get(flag)
	frappe.flags[flag] = True
	try:
		yield
	finally:
		frappe.flags[flag] = original


@contextmanager
def sidebarless_module(name, app="frappe"):
	"""A `Module Def` with no `Module Sidebar` -- the ordinary state, since nothing writes one.

	Deliberately does not delete any `Module Sidebar` on the way in: `TestNothingWritesASidebar`
	asserts there is none, and a helper that swept first would launder the thing under test.
	"""
	with no_developer_mode():
		frappe.get_doc({"doctype": "Module Def", "module_name": name, "app_name": app}).insert()
	clear_computed_base_cache(name)

	try:
		yield name
	finally:
		with no_developer_mode():
			frappe.delete_doc("Module Def", name, force=True, ignore_missing=True)
		# redis outlives the test's DB rollback, so a base computed from fixtures that are
		# about to vanish would leak into whatever runs next
		clear_computed_base_cache(name)


def make_report(module: str, name: str):
	"""Something for a computed base to be built out of, in `module`.

	A Report, not a DocType: creating a DocType issues DDL, which commits, so the fixture
	would outlive the test's rollback and strand content on a module that no longer exists.
	"""
	return frappe.get_doc(
		{
			"doctype": "Report",
			"report_name": name,
			"ref_doctype": "ToDo",
			"report_type": "Report Builder",
			"module": module,
			"is_standard": "No",
		}
	).insert(ignore_permissions=True)


def make_page(module: str, name: str):
	"""Something in `module` that can be *renamed* -- a Report cannot be.

	`Page.validate` refuses *any* new page outside developer mode, `standard: No` included,
	and the test site does not have it on. Nothing is written to disk: the export is gated on
	`standard == "Yes"`.
	"""
	with developer_mode():
		return frappe.get_doc(
			{
				"doctype": "Page",
				"page_name": name,
				"title": name,
				"module": module,
				"standard": "No",
			}
		).insert(ignore_permissions=True)


def delete_page(name: str):
	"""`Page.on_trash` refuses outside developer mode exactly as `validate` refuses the insert,
	so a page a test created has to be removed the way it was made."""
	with developer_mode():
		frappe.delete_doc("Page", name, force=True, ignore_missing=True)


def make_sidebar(module: str, **kwargs):
	"""A `Module Sidebar` authored by hand -- nothing writes one on a module's behalf.

	In developer mode because that is the only way one is ever authored: the document is app
	content, and on a customer site every one of them arrived by import.
	"""
	doc = frappe.new_doc("Module Sidebar")
	doc.module = module
	doc.update(kwargs)
	doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"})
	with developer_mode():
		return doc.insert(ignore_permissions=True)


@contextmanager
def module_resolvable_on_disk(module, app="frappe"):
	"""Make `module` resolve to a path, then take it back down.

	`export_to_files` -> `get_module_path` resolves via `frappe.local.module_app`, which is
	built from the app's modules.txt. Registering the module in memory instead of writing
	that file keeps the working tree clean when the test rolls back.
	"""
	import os
	import shutil

	scrubbed = frappe.scrub(module)
	path = frappe.get_app_path(app, scrubbed)

	# `get_pymodule_path` imports the package, so the folder has to be a real one
	os.makedirs(path, exist_ok=True)
	open(os.path.join(path, "__init__.py"), "a").close()

	frappe.local.module_app[scrubbed] = app
	frappe.local.app_modules.setdefault(app, [])
	added = scrubbed not in frappe.local.app_modules[app]
	if added:
		frappe.local.app_modules[app].append(scrubbed)

	try:
		yield path
	finally:
		shutil.rmtree(path, ignore_errors=True)
		frappe.local.module_app.pop(scrubbed, None)
		if added:
			frappe.local.app_modules[app].remove(scrubbed)


class TestItemIdentity(IntegrationTestCase):
	"""What makes two sidebar rows the same item, and what that identity is made of.

	A linked row's four columns *are* its identity, so a rename repairs it. An unlinked row has
	nothing to repair and keeps a stored key. These pin both halves.
	"""

	def test_a_linked_row_is_identified_by_its_columns(self):
		"""No hash, no stored id: the value is the columns, which is what leaves the link
		column free to be repaired by an ordinary Dynamic Link rename."""
		row = {"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"}

		self.assertEqual(item_key(row), "Link|DocType|User|")

	def test_identity_ignores_the_label_of_a_linked_row(self):
		"""Renaming an item in the sidebar must not orphan a user's delta."""
		self.assertEqual(
			item_key({"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"}),
			item_key({"type": "Link", "link_type": "DocType", "link_to": "User", "label": "People"}),
		)

	def test_identity_follows_a_renamed_target(self):
		"""The other half of that: the identity *does* move when the target does, which is why
		base row and delta row -- both rewritten by the rename -- still match afterwards."""
		before = item_key({"type": "Link", "link_type": "Report", "link_to": "Old Name"})
		after = item_key({"type": "Link", "link_type": "Report", "link_to": "New Name"})

		self.assertNotEqual(before, after)

	def test_a_stored_key_never_beats_a_link(self):
		"""A key stored beside the columns could only be a staler second answer -- it would
		survive a rename still naming what the row used to point at."""
		row = {"type": "Link", "link_type": "DocType", "link_to": "User", "key": "stale-0"}

		self.assertEqual(item_key(row), item_key({k: v for k, v in row.items() if k != "key"}))

	def test_unlinked_rows_are_told_apart_by_their_label(self):
		"""Every Section Break used to collide, which is what the ordinal was for. Including
		the label removes the collision instead -- and with it the ordinal, which re-anchored
		every delta below any insertion."""
		sections = [{"type": "Section Break", "label": f"S{i}"} for i in range(4)]

		self.assertEqual(len({item_key(row) for row in sections}), 4)

	def test_an_unlinked_row_keeps_a_stored_key(self):
		"""It is how a *customization* row names a Section Break: there are no link columns to
		name it by, and its label is a field the customization may itself override."""
		row = {"type": "Section Break", "label": "Reports", "key": "abc1234567"}

		self.assertEqual(item_key(row), "abc1234567")

	def test_the_key_assignment_pass_is_gone(self):
		"""Identity is derived from columns the row already carries, so nothing writes a key
		into a base row on save, and nothing re-keys one on re-authoring."""
		from frappe.desk.doctype.module_sidebar import module_sidebar

		for retired in ("derive_key", "assign_keys", "boot_dedupe_key", "BOOT_DEDUPE_FIELDS"):
			self.assertFalse(hasattr(module_sidebar, retired), f"{retired} should have been deleted")

		self.assertFalse(hasattr(frappe.new_doc("Module Sidebar"), "validate_unique_keys"))

	def test_a_base_row_stores_no_key_at_all(self):
		"""Nothing to keep in step with the columns, so nothing is written -- and a key an
		older derivation left behind is cleared rather than honoured, so the same section is
		identified the same way on a site that has been upgraded and one that has not."""
		with sidebarless_module("Test Unkeyed Rows Module") as module:
			doc = make_sidebar(module)
			doc.append("items", {"type": "Section Break", "label": "Reports", "key": "9f8e7d6c5b-2"})
			with developer_mode():
				doc.save(ignore_permissions=True)

			self.assertEqual([row.key for row in doc.items], [None, None])
			self.assertEqual(item_key(doc.items[1]), item_key({"type": "Section Break", "label": "Reports"}))

	def test_boot_does_not_read_a_stale_key_off_a_base_row(self):
		"""Clearing on save retires them as each app re-imports its sidebar; until then the
		rows are still in the database, and the resolution must not pick them up."""
		from frappe.boot import get_sidebar_bases

		with sidebarless_module("Test Stale Key Module") as module:
			doc = make_sidebar(module)
			# behind `validate`'s back, the way a row written by the old derivation still looks
			frappe.db.set_value(
				"Module Sidebar Item", doc.items[0].name, "key", "9f8e7d6c5b-0", update_modified=False
			)

			base = get_sidebar_bases([module])[module]

			self.assertIsNone(base.rows[0].get("key"))
			self.assertEqual(item_key(base.rows[0]), "Link|DocType|User|")


class TestModuleSidebarMerge(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Module Def", MODULE):
			with no_developer_mode():
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": MODULE, "app_name": "frappe"}
				).insert()
		self.archived = []

	def tearDown(self):
		# `delete_doc`, not `db.delete`: the latter leaves the item rows behind, and since a
		# sidebar is named after its module the next one to be inserted adopts the orphans
		for name in frappe.get_all("Module Sidebar", filters={"module": MODULE}, pluck="name"):
			frappe.delete_doc("Module Sidebar", name, force=True, ignore_permissions=True)
		for name in frappe.get_all("Custom Module Sidebar", filters={"module": MODULE}, pluck="name"):
			frappe.delete_doc("Custom Module Sidebar", name, force=True, ignore_permissions=True)
		for name in self.archived:
			frappe.delete_doc("Workspace Sidebar", name, force=True, ignore_missing=True)
		with no_developer_mode():
			frappe.delete_doc("Module Def", MODULE, force=True, ignore_missing=True)

	def make_workspace(self, name, items, for_user=None):
		"""One of this site's authored sidebars, where a v16 site keeps them.

		Inserted under `in_patch` because the archive takes no new entries -- the only writes
		it still accepts are the system's own, and a fixture standing in for what a v16 site
		already holds is exactly that.
		"""
		with system_write("in_patch"):
			doc = frappe.get_doc(
				{
					"doctype": "Workspace Sidebar",
					"title": name,
					"module": MODULE,
					"for_user": for_user,
					"items": items,
				}
			).insert(ignore_permissions=True)
		self.archived.append(doc.name)
		return doc

	def link(self, doctype, label=None):
		return {"type": "Link", "link_type": "DocType", "link_to": doctype, "label": label or doctype}

	def site_layer(self):
		return frappe.get_doc(
			"Custom Module Sidebar",
			frappe.db.get_value("Custom Module Sidebar", {"module": MODULE, "user": ""}),
		)

	def test_largest_sidebar_becomes_primary(self):
		"""`sequence_id` is near-uniform on a real site, so as the primary signal it picks
		arbitrarily -- it hands Accounts to Invoicing(28) over Accounting(49)."""
		self.make_workspace("TSM Small", [self.link("User")])
		self.make_workspace("TSM Large", [self.link("Role"), self.link("DocType")])

		sources = get_module_sidebar_sources()[MODULE]
		self.assertEqual(pick_primary(MODULE, sources).name, "TSM Large")

	def test_secondary_becomes_collapsed_section(self):
		self.make_workspace("TSM Primary", [self.link("User"), self.link("Role")])
		self.make_workspace("TSM Second", [self.link("DocType")])

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		sections = [i for i in plan["items"] if i["type"] == "Section Break"]

		self.assertEqual(len(sections), 1)
		self.assertEqual(sections[0]["label"], "TSM Second")
		self.assertEqual(sections[0]["keep_closed"], 1)
		# the secondary's own items are nested under it
		nested = [i for i in plan["items"] if i["source_workspace"] == "TSM Second" and i["type"] == "Link"]
		self.assertTrue(all(i["child"] == 1 for i in nested))

	def test_merged_title_is_the_module_name(self):
		"""The union of several sidebars is not any one source's title."""
		self.make_workspace("TSM Primary", [self.link("User"), self.link("Role")])
		self.make_workspace("TSM Second", [self.link("DocType")])

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		self.assertEqual(plan["title"], MODULE)

	def test_unmerged_title_keeps_the_workspace_label(self):
		"""A module with one sidebar must look exactly as it does today (`Loan Management`
		still reads "Lending")."""
		self.make_workspace("TSM Only", [self.link("User")])

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		self.assertEqual(plan["title"], "TSM Only")

	def test_boot_duplicates_are_dropped(self):
		"""The tables carry rows boot dedupes away; copying them straight across would show
		copies the desk does not. erpnext.site has 160 such rows, 72 in Core alone."""
		self.make_workspace(
			"TSM Dupes",
			[self.link("User"), self.link("User"), self.link("Role")],
		)

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		users = [i for i in plan["items"] if i["link_to"] == "User"]
		self.assertEqual(len(users), 1)

	def test_differently_labelled_duplicates_are_one_item(self):
		"""A relabelled duplicate used to survive the merge, because the dedupe key included
		`label`. Identity does not: two rows pointing at one target *are* one item, whatever
		the two workspaces called it (erpnext's CRM lists Lead twice).

		Keeping the second is no longer possible rather than no longer preferred -- it would
		share an identity with the first, so no customization could name one without naming the
		other, and the resolution drops it on the way to the payload regardless. The first
		wins, which is the label the desk was already showing at that position.
		"""
		self.make_workspace(
			"TSM Deliberate",
			[self.link("User", label="All Users"), self.link("User", label="Active Users")],
		)

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		users = [i for i in plan["items"] if i["link_to"] == "User"]
		self.assertEqual([i["label"] for i in users], ["All Users"])

	def test_merging_does_not_re_key_items(self):
		"""A delta made against a source workspace's item still names it after the merge: the
		merge copies the columns the identity is made of and derives nothing."""
		self.make_workspace("TSM Keyed", [self.link("User"), {"type": "Section Break", "label": "More"}])

		sources = get_module_sidebar_sources()[MODULE]
		plan = build_module_sidebar(MODULE, sources)

		self.assertEqual(
			[item_key(row) for row in sources[0].rows],
			[item_key(row) for row in plan["items"]],
		)

	def test_claim_flag_is_not_carried(self):
		"""The conversion drops the claim rather than mapping it to `is_default_module`.

		A converted row is unretractable: it lives only in the site database, the patch skips a
		module that already carries a layer, and no app ships a fixture that would overwrite it.
		Carrying the flag would give an app a claim its own author could never take back. An app
		that wants one flags the row in a `module_sidebar` fixture it ships."""
		item = self.link("User")
		item["default_workspace"] = 1
		self.make_workspace("TSM Default", [item])

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		self.assertFalse(plan["items"][0].get("is_default_module"))
		self.assertNotIn("default_workspace", plan["items"][0])

	def test_provenance_is_recorded(self):
		"""`merged_from` plus per-item `source_workspace` are what make the merge reversible,
		so splitting a module later is a command rather than a second migration."""
		self.make_workspace("TSM Primary", [self.link("User"), self.link("Role")])
		self.make_workspace("TSM Second", [self.link("DocType")])

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		self.assertEqual(sorted(json.loads(plan["merged_from"])), ["TSM Primary", "TSM Second"])
		self.assertEqual({i["source_workspace"] for i in plan["items"]}, {"TSM Primary", "TSM Second"})

	def test_a_merge_lands_in_the_site_layer(self):
		"""Not in a `Module Sidebar`. That document means "an app ships this", and a merge is
		derived from this site's own data -- it is site intent, so it goes where site intent
		lives and stays a layer over the module's computed base."""
		self.make_workspace("TSM Only", [self.link("User")])
		build_all()

		self.assertFalse(frappe.db.exists("Module Sidebar", {"module": MODULE}))
		self.assertTrue(self.site_layer().sidebar_items)

	def test_an_item_the_base_already_has_is_stored_as_a_reference(self):
		"""Which is what keeps a migrated sidebar maintained rather than frozen: the label and
		the link keep coming from below, so the app's next relabel still reaches it."""
		make_report(MODULE, "TSM Migrated Report")
		clear_computed_base_cache(MODULE)
		self.make_workspace(
			"TSM Mixed",
			[
				{"type": "Link", "link_type": "Report", "link_to": "TSM Migrated Report", "label": "R"},
				self.link("User"),
			],
		)
		build_all()

		rows = {row.link_to: row.added for row in self.site_layer().sidebar_items}
		# in the module's contents, so the base has it -- a reference
		self.assertEqual(rows["TSM Migrated Report"], 0)
		# nothing in this module points at User, so there is nothing below to refer to
		self.assertEqual(rows["User"], 1)

	def test_a_source_naming_a_module_the_site_no_longer_has_is_left_alone(self):
		"""A sidebar outlives the app that authored it: the archive keeps the module column of
		an app that has since been uninstalled, and a layer cannot be anchored to a module that
		is not there. The conversion has to walk past it -- one such row used to abort the whole
		patch, and with it every module after the dead one alphabetically."""
		self.make_workspace("TSM Gone", [self.link("User")])
		self.make_workspace("TSM Gone Fork", [self.link("Role")], for_user="test@example.com")
		# `db.delete`, not `delete_doc`: what an uninstall leaves behind is the row's absence,
		# and delete_doc would refuse while the archive still links to it
		frappe.db.delete("Module Def", {"name": MODULE})

		result = build_all()

		self.assertNotIn(MODULE, [plan["module"] for plan in result["merged"]])
		self.assertNotIn(MODULE, [fork["module"] for fork in result["personal"]])
		self.assertFalse(frappe.db.exists("Custom Module Sidebar", {"module": MODULE}))
		# the sources stay, so reinstalling the app is what brings them back
		self.assertEqual(frappe.db.count("Workspace Sidebar", {"module": MODULE}), 2)

	def test_build_is_idempotent(self):
		self.make_workspace("TSM Only", [self.link("User")])

		build_all()
		first = self.site_layer()
		first_items = [(item_key(i), i.link_to) for i in first.sidebar_items]

		build_all()
		second = self.site_layer()

		self.assertEqual(first.creation, second.creation)
		self.assertEqual(first_items, [(item_key(i), i.link_to) for i in second.sidebar_items])

	def test_a_site_owned_row_cannot_be_made_standard_by_hand(self):
		"""`standard` means backed by a file. Setting it without writing one leaves a row that
		orphan removal deletes on the next migrate, so validate refuses it outright."""
		doc = make_sidebar(MODULE)
		self.assertEqual(doc.standard, 0)
		with self.assertRaises(frappe.ValidationError):
			doc.standard = 1
			doc.save()

	def test_site_owned_row_survives_orphan_removal(self):
		"""Orphan removal only considers standard rows -- a site-owned sidebar has no file by
		definition and must never be mistaken for one whose file went missing."""
		from frappe.model.sync import remove_orphan_entities

		make_sidebar(MODULE)
		remove_orphan_entities("Module Sidebar")
		self.assertTrue(frappe.db.exists("Module Sidebar", MODULE))

	def test_deleting_the_module_removes_its_sidebar(self):
		make_sidebar(MODULE)
		frappe.delete_doc("Module Def", MODULE, force=True)
		self.assertFalse(frappe.db.exists("Module Sidebar", MODULE))

	def test_items_may_come_from_any_module(self):
		"""A sidebar's items are deliberately NOT constrained to its module.

		Authors group by what belongs together in navigation, which is not the same as what
		a module owns -- and this flexibility is why splitting a module later needs no
		tooling. Pinned so nobody adds a well-meaning validation.
		"""
		sidebar = frappe.new_doc("Module Sidebar")
		sidebar.module = MODULE
		# User is Core, Report is Core, Workspace is Desk -- none of them this module
		for item in (self.link("User"), self.link("Report"), self.link("DocType")):
			sidebar.append("items", item)
		# authored by hand, so in developer mode -- the document is app content
		with developer_mode():
			sidebar.insert(ignore_permissions=True)

		self.assertEqual(len(frappe.get_doc("Module Sidebar", MODULE).items), 3)

	def test_identities_survive_export_and_reimport(self):
		"""Export to JSON, re-import twice, and assert the deltas would still resolve.

		This is the property item identity exists for. `import_doc` is delete-then-insert and
		child rows are hash-named, so every re-import produces different row `name`s -- a
		customization anchored on `name` would break on every `bench migrate`. Anchored on the
		row's own columns it survives, because nothing about them is generated.
		"""
		import os

		from frappe.modules.import_file import import_file_by_path

		doc = make_sidebar(MODULE)
		with developer_mode():
			doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "Role"})
			doc.append("items", {"type": "Section Break", "label": "More"})
			doc.save(ignore_permissions=True)

		# only a standard row exports
		doc.db_set("standard", 1, update_modified=False)
		doc.reload()

		before = {item_key(i): i.link_to for i in doc.items}
		names_before = {i.name for i in doc.items}
		self.assertTrue(before, "sanity: the sidebar had items")

		scrubbed = frappe.scrub(MODULE)
		with module_resolvable_on_disk(MODULE) as module_path, developer_mode():
			doc.export_sidebar()

			path = os.path.join(module_path, "module_sidebar", scrubbed, f"{scrubbed}.json")
			self.assertTrue(os.path.exists(path), f"export did not write {path}")

			for _ in range(2):
				import_file_by_path(path, force=True, ignore_version=True)

			after_doc = frappe.get_doc("Module Sidebar", MODULE)
			after = {item_key(i): i.link_to for i in after_doc.items}
			names_after = {i.name for i in after_doc.items}

		self.assertEqual(before, after, "identities must be identical across re-import")
		self.assertNotEqual(names_before, names_after, "sanity: child row names are regenerated")

	def test_the_archive_survives_the_conversion(self):
		"""The rule the whole upgrade is built on: log when the source survives, refuse only
		when something is destroyed. Every source row is kept, so the second clause never
		fires -- and a site migrated by a bad build can be migrated again from the same rows."""
		self.make_workspace("TSM Only", [self.link("User")])
		before = frappe.db.count("Workspace Sidebar"), frappe.db.count("Workspace Sidebar Item")

		build_all()

		self.assertEqual(
			before, (frappe.db.count("Workspace Sidebar"), frappe.db.count("Workspace Sidebar Item"))
		)


class TestModuleSidebarStandard(IntegrationTestCase):
	"""`standard` is the export switch, and marking flips it by writing the file.

	Marking a module's sidebar standard is materialize-and-export: it takes the base the module
	already has -- computed from its contents when no app shipped one -- writes it as a
	document and exports it, so an author starts from what the desk shows rather than from
	nothing. Un-marking deletes the document, which hands the module back to that computed
	base in the same request.

	The file is the whole point. `standard` means "backed by a JSON file in an app", and orphan
	removal deletes a standard record whose file is missing -- so a half-done mark is a row
	that destroys itself on the next migrate.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Module Def", MODULE):
			with no_developer_mode():
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": MODULE, "app_name": "frappe"}
				).insert()
		self.clear_module_content()
		clear_computed_base_cache(MODULE)
		self.addCleanup(clear_computed_base_cache, MODULE)

	def tearDown(self):
		frappe.set_user("Administrator")
		self.clear_module_content()
		with no_developer_mode():
			frappe.delete_doc("Module Def", MODULE, force=True, ignore_missing=True)
		# `remove_orphan_entities` commits, so anything these tests wrote before it is already
		# durable and the framework's rollback will not undo it. Commit the cleanup too, or a
		# standard row for a module with no folder outlives the test and breaks every later
		# save of it.
		frappe.db.commit()  # nosemgrep

	def clear_module_content(self):
		"""Everything these tests put in the module, sidebar and contents alike.

		Both ends, because the commit in `tearDown` puts this suite's fixtures beyond the
		framework's rollback: a Report left behind points at a module that no longer exists and
		turns up in the next test's computed base.

		`delete_doc`, not `frappe.db.delete`: the sidebar is named after its module, so item
		rows left behind by a raw delete are inherited by the next document of the same name.
		"""
		for name in frappe.get_all("Module Sidebar", filters={"module": MODULE}, pluck="name"):
			frappe.delete_doc("Module Sidebar", name, force=True, ignore_permissions=True)
		frappe.db.delete("Report", {"module": MODULE})

	def with_content(self):
		"""Something for the module's computed base to be built out of."""
		make_report(MODULE, "Test Standard Sidebar Report")
		clear_computed_base_cache(MODULE)

	def exported_json(self, path):
		"""The exported file, minus what the framework stamps on every write.

		Two exports of the same sidebar differ in their timestamps and nothing else, so the
		comparison has to drop them to say anything about the content.
		"""
		with open(path) as f:
			content = json.load(f)
		for field in ("creation", "modified", "modified_by", "owner", "docstatus", "idx"):
			content.pop(field, None)
		return content

	def test_marking_a_module_with_no_document_ships_its_computed_base(self):
		"""The materialize half. Nothing persists a base, so the ordinary state of a module is
		to have no document at all -- and marking it standard has to produce one out of what
		the desk is already rendering, rather than an empty shell to fill in by hand."""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			base = get_computed_base(MODULE)
			self.assertFalse(frappe.db.exists("Module Sidebar", MODULE))

			name = mark_as_standard(MODULE)

			doc = frappe.get_doc("Module Sidebar", name)
			self.assertEqual(doc.standard, 1)
			self.assertEqual(doc.app, "frappe")
			self.assertTrue(os.path.exists(doc.exported_file_path()))
			self.assertEqual(doc.title, base.title)
			self.assertEqual(doc.header_icon, base.header_icon)
			self.assertEqual(
				[(item_key(row), row.type, row.link_to) for row in doc.items],
				[(item_key(row), row.type, row.link_to) for row in base.rows],
			)

	def test_marking_an_authored_document_exports_it_as_it_stands(self):
		"""A module that already has a document is shipped verbatim: the computed base is what
		you get when there is nothing to ship, not something that overwrites authored items."""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			doc = make_sidebar(MODULE)
			self.assertEqual(doc.standard, 0)

			mark_as_standard(MODULE)

			doc.reload()
			self.assertEqual(doc.standard, 1)
			self.assertEqual(doc.app, "frappe")
			self.assertTrue(os.path.exists(doc.exported_file_path()))
			self.assertEqual([row.link_to for row in doc.items], ["User"])

	def test_marking_a_document_with_no_items_ships_the_computed_base(self):
		"""An empty items table is not what the desk renders for the module -- boot fills those
		rows in from the computed base too -- so shipping the document as it stands would ship a
		file that does not match the navigation it was adopted from."""
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			stub = frappe.new_doc("Module Sidebar")
			stub.module = MODULE
			stub.title = "Named by hand"
			stub.insert(ignore_permissions=True)
			self.assertEqual(stub.items, [])

			mark_as_standard(MODULE)

			stub.reload()
			# its own title stands: that is authored, and only the items were missing
			self.assertEqual(stub.title, "Named by hand")
			self.assertEqual(
				[item_key(row) for row in stub.items],
				[item_key(row) for row in get_computed_base(MODULE).rows],
			)

	def test_a_standard_row_whose_file_went_missing_is_written_again(self):
		"""The mark reports what it verified, so being asked again to ship a sidebar that has
		lost its file has to write the file rather than report the row as already done -- a
		standard row without one is deleted by the next migrate."""
		import os
		import shutil

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			path = frappe.get_doc("Module Sidebar", name).exported_file_path()
			shutil.rmtree(os.path.dirname(path))

			mark_as_standard(MODULE)

			self.assertTrue(os.path.exists(path))

	def test_standard_row_survives_orphan_removal(self):
		"""The whole point of writing the file: a standard row without one is an orphan."""
		from frappe.model.sync import remove_orphan_entities

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)

			remove_orphan_entities("Module Sidebar")
			self.assertTrue(frappe.db.exists("Module Sidebar", name))

	def test_the_mark_fails_when_the_export_wrote_no_file(self):
		"""Verified, not assumed. A standard row with nothing backing it is an orphan that the
		next migrate deletes, so a mark that could not write its file has to leave the module
		exactly as it found it -- with no document at all."""
		from unittest.mock import patch

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			with patch("frappe.modules.export_file.export_to_files"):
				with self.assertRaises(frappe.ValidationError):
					mark_as_standard(MODULE)

		self.assertFalse(frappe.db.exists("Module Sidebar", MODULE))

	def test_marking_needs_developer_mode(self):
		"""Only developer mode writes files, so outside it the mark could only produce a row
		that deletes itself."""
		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			mark_as_standard(MODULE)

		self.assertFalse(frappe.db.exists("Module Sidebar", MODULE))

	def test_un_marking_needs_developer_mode(self):
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)

			with no_developer_mode(), self.assertRaises(frappe.ValidationError):
				unmark_as_standard(MODULE)

			self.assertTrue(frappe.db.exists("Module Sidebar", name))

	def test_neither_needs_a_role(self):
		"""The old `Workspace Manager` gate is gone: developer mode is the whole gate, and what
		is left is the doctype's own permissions. A System Manager holds no `Workspace Manager`
		role and is refused nothing here."""
		self.enterContext(self.set_user("test@example.com"))
		self.assertNotIn("Workspace Manager", frappe.get_roles())

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			self.assertTrue(frappe.db.exists("Module Sidebar", name))

			unmark_as_standard(MODULE)
			self.assertFalse(frappe.db.exists("Module Sidebar", name))

	def test_cannot_mark_standard_when_the_module_has_no_folder(self):
		"""No folder, nowhere to write the file -- and a standard row without one is an
		orphan, so refuse before creating anything."""
		with developer_mode(), self.assertRaises(frappe.ValidationError):
			mark_as_standard(MODULE)

		self.assertFalse(frappe.db.exists("Module Sidebar", MODULE))

	def test_un_marking_deletes_the_document_and_its_file(self):
		"""Not a cleared flag: a row that is neither app content nor site intent is a frozen
		copy of a base that has stopped tracking the module. And the file has to go too --
		left behind, the next `bench migrate` re-imports it and marks the row standard again."""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			path = frappe.get_doc("Module Sidebar", name).exported_file_path()
			self.assertTrue(os.path.exists(path))

			unmark_as_standard(MODULE)

			self.assertFalse(frappe.db.exists("Module Sidebar", name))
			self.assertFalse(os.path.exists(path))

	def test_un_marking_returns_the_module_to_its_computed_base(self):
		"""In the same request. The document going away is not the module losing its
		navigation -- the base is computed from the module's contents on read."""
		from frappe.boot import get_sidebar_bases

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			mark_as_standard(MODULE)
			unmark_as_standard(MODULE)

			base = get_sidebar_bases([MODULE])[MODULE]

			self.assertIsNone(base.get("name"), "a computed base has no document")
			self.assertEqual(
				[item_key(row) for row in base.rows],
				[item_key(row) for row in get_computed_base(MODULE).rows],
			)

	def test_a_round_trip_leaves_no_residue(self):
		"""Mark, un-mark, mark again: the same file, and nothing accumulated in between."""
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			path = frappe.get_doc("Module Sidebar", name).exported_file_path()
			first = self.exported_json(path)

			unmark_as_standard(MODULE)
			self.assertEqual(frappe.get_all("Module Sidebar", filters={"module": MODULE}), [])

			again = mark_as_standard(MODULE)

			self.assertEqual(again, name)
			self.assertEqual(self.exported_json(path), first)
			self.assertEqual(len(frappe.get_all("Module Sidebar", filters={"module": MODULE})), 1)

	def test_marking_standard_is_idempotent(self):
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			modified = frappe.db.get_value("Module Sidebar", name, "modified")

			mark_as_standard(MODULE)
			self.assertEqual(frappe.db.get_value("Module Sidebar", name, "modified"), modified)


APP_CONTENT_MODULE = "Test App Content Sidebar Module"


class TestModuleSidebarIsAppContent(IntegrationTestCase):
	"""A `Module Sidebar` belongs to an app, not to the site holding it.

	Only developer mode writes one, and the invariant that buys is what makes app updates safe:
	*on a non-developer-mode site every sidebar document arrived by import*, so overwriting one
	on an app update costs the site nothing. Site intent has nowhere to hide in the document
	because it cannot get in.

	It goes where it already went instead -- `Custom Module Sidebar`, at the site-wide
	layer or the user's own -- which is what closes "two ways to author the same sidebar with no
	stated boundary".
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.module = self.enterContext(sidebarless_module(APP_CONTENT_MODULE))

	def new_sidebar(self):
		doc = frappe.new_doc("Module Sidebar")
		doc.module = self.module
		doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
		return doc

	def make_workspace(self, title):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": title,
				"module": self.module,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		return doc

	def roleless_user(self):
		"""Somebody the old `Workspace Manager` gate would have turned away.

		Made here rather than picked out of the test records: the shared ones carry whatever
		roles other suites needed, and this test's whole claim is about holding none.
		"""
		email = "test-sidebar-nobody@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc({"doctype": "User", "email": email, "first_name": "Nobody"}).insert(
				ignore_permissions=True
			)
		return email

	def test_a_desk_user_may_only_read_a_sidebar(self):
		"""An ordinary desk user reads the sidebar the app shipped and writes their own delta
		instead. Their create/write/delete on this doctype was revoked to `read`."""
		perms = {perm.role: perm for perm in frappe.get_meta("Module Sidebar").permissions}
		desk_user = perms.get("Desk User")

		self.assertIsNotNone(desk_user, "Desk User must still be able to read a sidebar")
		self.assertTrue(desk_user.read)
		self.assertFalse(desk_user.create)
		self.assertFalse(desk_user.write)
		self.assertFalse(desk_user.delete)

	def test_a_customer_site_cannot_write_a_sidebar(self):
		"""Not even as Administrator, and not with permissions ignored: the gate is developer
		mode, not who is asking. This is the invariant stated as a test."""
		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			self.new_sidebar().insert(ignore_permissions=True)

		self.assertFalse(frappe.db.exists("Module Sidebar", {"module": self.module}))

	def test_a_system_manager_is_no_more_privileged_than_anyone_else(self):
		"""'Regardless of role' includes the roles that can do everything else on a site."""
		self.enterContext(self.set_user("test@example.com"))
		self.assertIn("System Manager", frappe.get_roles())

		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			self.new_sidebar().insert(ignore_permissions=True)

	def test_editing_an_imported_sidebar_is_refused_too(self):
		"""The gate is on writing, not only on creating. A sidebar that arrived by import stays
		as the app wrote it, which is the half of the invariant app updates actually rest on."""
		with system_write():
			imported = self.new_sidebar().insert(ignore_permissions=True)

		imported.title = "Edited by the site"
		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			imported.save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Module Sidebar", imported.name, "title"), self.module)

	def test_developer_mode_needs_no_role(self):
		"""The same call the customer site refuses, with developer mode on and nothing else
		different -- made by a user holding no roles at all, because developer mode is the whole
		gate and there is no role check behind it."""
		self.enterContext(self.set_user(self.roleless_user()))
		self.assertNotIn("Workspace Manager", frappe.get_roles())

		with developer_mode():
			doc = self.new_sidebar().insert(ignore_permissions=True)

		self.assertTrue(frappe.db.exists("Module Sidebar", doc.name))

	def test_an_import_still_writes_on_a_customer_site(self):
		"""How every sidebar on a customer site gets there. Each of these routes is the system
		placing app content, so gating them would mean an app that ships a sidebar could not be
		installed or updated anywhere."""
		for flag in SYSTEM_WRITE_FLAGS:
			with self.subTest(flag=flag):
				with no_developer_mode(), system_write(flag):
					doc = self.new_sidebar().insert(ignore_permissions=True)

				self.assertTrue(frappe.db.exists("Module Sidebar", doc.name))
				frappe.delete_doc("Module Sidebar", doc.name, force=True)

	def test_the_site_keeps_saying_what_it_wants(self):
		"""The point of shutting the document: site intent has somewhere better to go, and it
		still goes there on a site that can no longer touch the document at all."""
		from frappe.desk.doctype.custom_module_sidebar.custom_module_sidebar import (
			get_customization,
			save_site_sidebar,
		)

		with no_developer_mode():
			save_site_sidebar(self.module, items=[{"key": "whatever", "hidden": 1}])

		site_layer = get_customization(self.module, None)
		self.assertIsNotNone(site_layer)
		self.addCleanup(
			frappe.delete_doc,
			"Custom Module Sidebar",
			site_layer.name,
			force=True,
			ignore_permissions=True,
		)
		self.assertEqual([(row.key, row.hidden) for row in site_layer.sidebar_items], [("whatever", 1)])

	def test_a_new_workspace_links_itself_through_the_site_layer(self):
		"""The one runtime path that used to write the document. Creating a workspace in a
		module that ships a sidebar has to keep working on a customer site -- and the link it
		earns is site intent, so it belongs in the site layer rather than in app content."""
		from frappe.desk.doctype.custom_module_sidebar.custom_module_sidebar import (
			get_customization,
		)
		from frappe.desk.doctype.workspace.workspace import add_to_module_sidebar

		with system_write():
			shipped = self.new_sidebar().insert(ignore_permissions=True)

		# two, because the module's landing page is the first item of this list -- so the one
		# being linked here is deliberately not the one the module opens on
		self.make_workspace("Test App Content Home")
		workspace = self.make_workspace("Test App Content Workspace")

		with no_developer_mode():
			add_to_module_sidebar(workspace)

		site_layer = get_customization(self.module, None)
		self.assertIsNotNone(site_layer, "the link has to land somewhere")
		self.addCleanup(
			frappe.delete_doc,
			"Custom Module Sidebar",
			site_layer.name,
			force=True,
			ignore_permissions=True,
		)
		self.assertEqual(
			[(row.link_type, row.link_to) for row in site_layer.sidebar_items if row.added],
			[("Workspace", workspace.name)],
		)
		# and the app's own sidebar is exactly as the app wrote it
		shipped.reload()
		self.assertEqual([row.link_to for row in shipped.items], ["ToDo"])

	def test_a_private_workspace_links_itself_through_nothing(self):
		"""The other side of the same branch (D3). A private page's link is derived on read
		from the workspace itself, so writing one would put a row per private page into the
		document the whole site shares -- and put it there for an admin to find while curating
		everyone's navigation."""
		from frappe.desk.doctype.custom_module_sidebar.custom_module_sidebar import (
			get_customization,
		)
		from frappe.desk.doctype.workspace.workspace import add_to_module_sidebar

		with system_write():
			self.new_sidebar().insert(ignore_permissions=True)

		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "Test Private App Content Workspace",
				"label": f"Test Private App Content Workspace-{frappe.session.user}",
				"module": self.module,
				"public": 0,
				"for_user": frappe.session.user,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", workspace.name, force=True, ignore_missing=True)

		with no_developer_mode():
			add_to_module_sidebar(workspace)

		self.assertIsNone(get_customization(self.module, None), "nothing may be written for it")

	def test_a_page_that_stops_being_private_earns_the_link_it_never_stored(self):
		"""The branch is on what the workspace *is*, not on when it was created: a page that
		has just been shared has stopped having a derived link, so this is where it gains a
		stored one -- otherwise sharing a page would take away the only way into it."""
		from frappe.desk.doctype.custom_module_sidebar.custom_module_sidebar import (
			get_customization,
		)
		from frappe.desk.doctype.workspace.workspace import update_workspace_settings

		with system_write():
			self.new_sidebar().insert(ignore_permissions=True)

		title = "Test Shared After The Fact"
		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": f"{title}-{frappe.session.user}",
				"module": self.module,
				"public": 0,
				"for_user": frappe.session.user,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", title, force=True, ignore_missing=True)
		self.addCleanup(frappe.delete_doc, "Workspace", workspace.name, force=True, ignore_missing=True)

		with no_developer_mode():
			update_workspace_settings(workspace.name, access="public")

		site_layer = get_customization(self.module, None)
		self.assertIsNotNone(site_layer)
		self.addCleanup(
			frappe.delete_doc,
			"Custom Module Sidebar",
			site_layer.name,
			force=True,
			ignore_permissions=True,
		)
		self.assertEqual(
			[row.link_to for row in site_layer.sidebar_items if row.added],
			# the shared name, not the one it carried while it was private
			[title],
		)


class TestNothingWritesASidebar(IntegrationTestCase):
	"""No path writes a `Module Sidebar` on a module's behalf.

	Persisting a generated row was what made an app that *stops* shipping a sidebar leave its
	module un-navigable until the next migrate, and it left rows behind to be orphaned when a
	module or an app went away. The computed base replaced the need for it, so the write is
	gone: a module either has a document because someone authored or shipped one, or it has
	none at all.
	"""

	def setUp(self):
		frappe.set_user("Administrator")

	def rows_for(self, module):
		return frappe.get_all("Module Sidebar", filters={"module": module}, pluck="name")

	def test_a_new_module_gets_no_sidebar_document(self):
		"""What installing an app does, one module at a time: the Module Defs land and nothing
		follows them. The module is navigable regardless -- its base is computed."""
		with sidebarless_module("Test Unwritten Sidebar Module") as module:
			self.assertEqual(self.rows_for(module), [])
			self.assertEqual(get_computed_base(module).module, module)

	def test_a_build_writes_no_row_for_a_module_that_ships_none(self):
		"""What a migrate does. A module with no authored workspaces has nothing to merge, so
		the build has nothing to say about it -- and must not invent a row."""
		with sidebarless_module("Test Unbuilt Sidebar Module") as module:
			make_report(module, "Test Unbuilt Report")

			with developer_mode():
				build_all()

			self.assertEqual(self.rows_for(module), [])

	def test_the_dry_run_names_the_modules_it_leaves_computed(self):
		"""The build no longer writes these rows, but the plan still has to account for the
		modules it is walking past -- otherwise "0 merged" reads as "0 modules"."""
		with sidebarless_module("Test Reported Sidebar Module") as module:
			result = build_all(dry_run=True)

			self.assertIn(module, result["computed"])


COMPUTED_MODULE = "Test Computed Sidebar Module"


class TestComputedSidebarBase(IntegrationTestCase):
	"""A module nobody shipped a sidebar for is navigable anyway: the system computes its
	base from the module's own contents and site-caches it.

	Per D4 a base has exactly two origins -- shipped as an app's JSON, or computed here --
	and only the shipped route is meant to persist a document. So this route has to hold up
	without one: it produces the base fresh, and the cache in front of it has to fall the
	moment the module's contents change.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.module = self.enterContext(sidebarless_module(COMPUTED_MODULE))

	def make_report(self, name):
		return make_report(self.module, name)

	def make_page(self, name):
		return make_page(self.module, name)

	def links(self, base):
		return [(row.link_type, row.link_to) for row in base.rows]

	def test_the_base_is_built_from_the_module_contents(self):
		"""Nothing shipped a sidebar, so the module's own doctypes, reports and pages are the
		navigation. Shaped like a stored base so boot cannot tell the two apart."""
		self.make_report("Test Computed Report")
		self.make_page("test-computed-page")

		base = get_computed_base(self.module)

		self.assertEqual(base.module, self.module)
		self.assertEqual(base.title, self.module)
		self.assertEqual(base.app, "frappe")
		self.assertIn(("Report", "Test Computed Report"), self.links(base))
		self.assertIn(("Page", "test-computed-page"), self.links(base))

	def test_nothing_is_persisted(self):
		"""The whole point of computing: with no row there is nothing to orphan when the
		module or its app goes away, and nothing to leave behind stale."""
		self.make_report("Test Unpersisted Report")

		get_computed_base(self.module)

		self.assertFalse(frappe.db.exists("Module Sidebar", {"module": self.module}))

	def test_items_are_identifiable(self):
		"""A delta anchors on a row's identity, so a computed base has to be customizable on
		the same terms as a shipped one -- every row identifiable, and no two alike."""
		self.make_report("Test Keyed Report")

		keys = [item_key(row) for row in get_computed_base(self.module).rows]

		self.assertTrue(all(keys))
		self.assertEqual(len(set(keys)), len(keys))

	def test_the_base_is_served_from_the_site_cache(self):
		"""Warm boot reads redis, not the module's contents -- which is what keeps the
		computed route affordable on a site with many sidebar-less modules."""
		self.make_report("Test Cached Report")
		get_computed_base(self.module)

		# a fresh worker: the request-local mirror is empty, so this has to come from redis
		frappe.local.cache.clear()
		with self.assertQueryCount(0):
			base = get_computed_base(self.module)

		self.assertIn(("Report", "Test Cached Report"), self.links(base))

	def test_a_new_report_reaches_the_navigation(self):
		"""The cache is busted by the module gaining content, so newly created content needs no
		migrate and no restart to show up."""
		get_computed_base(self.module)

		self.make_report("Test Late Report")

		self.assertIn(("Report", "Test Late Report"), self.links(get_computed_base(self.module)))

	def test_a_deleted_page_leaves_the_navigation(self):
		page = self.make_page("test-doomed-page")
		self.assertIn(("Page", page.name), self.links(get_computed_base(self.module)))

		delete_page(page.name)

		self.assertNotIn(("Page", page.name), self.links(get_computed_base(self.module)))

	def test_moving_content_busts_both_modules(self):
		"""A module loses what another gains, so an update touches two caches -- the one named
		on the document now and the one it named before."""
		report = self.make_report("Test Migrating Report")
		self.assertIn(("Report", report.name), self.links(get_computed_base(self.module)))

		report.module = "Core"
		report.save(ignore_permissions=True)
		self.addCleanup(clear_computed_base_cache, "Core")

		self.assertNotIn(("Report", report.name), self.links(get_computed_base(self.module)))
		self.assertIn(("Report", report.name), self.links(get_computed_base("Core")))

	def test_every_source_of_content_busts_the_cache(self):
		"""The invalidation set has to equal the read set. If `get_module_info` grows a source
		whose controller does not clear this cache, that source's bases go stale silently.

		Driven through `clear_cache` -- the one method the framework runs on both a save and a
		delete -- so this covers the DocType case without creating one; see `make_report` for
		why no test does.
		"""
		for doctype in MODULE_CONTENT_DOCTYPES:
			get_computed_base(self.module)
			self.assertIsNotNone(frappe.cache.hget(COMPUTED_BASE_CACHE_KEY, self.module))

			doc = frappe.new_doc(doctype)
			doc.module = self.module
			doc.clear_cache()

			self.assertIsNone(
				frappe.cache.hget(COMPUTED_BASE_CACHE_KEY, self.module),
				f"{doctype}.clear_cache() does not bust the computed sidebar base",
			)


class TestShippedDockOrder(IntegrationTestCase):
	"""`ship_dock_order`: the dock arrangement on screen becoming the one the app ships.

	The two layers a site can arrange -- `Dock Order` and `User.dock_modules` -- rearrange the
	list an app hands them. This writes that list, so what it produces has to be app content on
	disk, not site state: `sequence_id` on each module's `Module Sidebar`, exported.
	"""

	FIRST = "Test Ship Order Alpha"
	SECOND = "Test Ship Order Beta"

	def setUp(self):
		frappe.set_user("Administrator")
		for module in (self.FIRST, self.SECOND):
			if not frappe.db.exists("Module Def", module):
				with no_developer_mode():
					frappe.get_doc(
						{"doctype": "Module Def", "module_name": module, "app_name": "frappe"}
					).insert()
		self.wipe()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.wipe()
		for module in (self.FIRST, self.SECOND):
			with no_developer_mode():
				frappe.delete_doc("Module Def", module, force=True, ignore_missing=True)
		# same reason as `TestModuleSidebarStandard`: these tests write files and commit, so the
		# cleanup has to be durable too or a standard row outlives the module it names
		frappe.db.commit()  # nosemgrep

	def wipe(self):
		for module in (self.FIRST, self.SECOND):
			for name in frappe.get_all("Module Sidebar", filters={"module": module}, pluck="name"):
				frappe.delete_doc("Module Sidebar", name, force=True, ignore_permissions=True)
			clear_computed_base_cache(module)

	@contextmanager
	def both_modules_on_disk(self):
		with module_resolvable_on_disk(self.FIRST), module_resolvable_on_disk(self.SECOND):
			# something navigable in each, so neither is dropped from the payload for having
			# nothing the user can reach
			make_report(self.FIRST, "Test Ship Order Alpha Report")
			make_report(self.SECOND, "Test Ship Order Beta Report")
			clear_computed_base_cache(self.FIRST)
			clear_computed_base_cache(self.SECOND)
			try:
				yield
			finally:
				frappe.db.delete("Report", {"module": ["in", [self.FIRST, self.SECOND]]})

	def sequence_of(self, module):
		return frappe.db.get_value("Module Sidebar", {"module": module}, "sequence_id")

	def test_shipping_writes_a_sequence_and_exports_it(self):
		import os

		with self.both_modules_on_disk(), developer_mode():
			ship_dock_order([self.SECOND, self.FIRST])

			self.assertEqual(self.sequence_of(self.SECOND), 1)
			self.assertEqual(self.sequence_of(self.FIRST), 2)
			for module in (self.FIRST, self.SECOND):
				doc = frappe.get_doc("Module Sidebar", {"module": module})
				self.assertEqual(doc.standard, 1)
				self.assertTrue(os.path.exists(doc.exported_file_path()), "the order has to reach the app")

	def test_the_dock_order_follows(self):
		"""The point of the whole thing: `get_app_modules` is what the dock renders, so the
		arrangement has to come back out of it in the order that went in."""
		from frappe.boot import get_app_modules

		with self.both_modules_on_disk(), developer_mode():
			# alphabetical to begin with -- neither is in modules.txt, so nothing but the name
			# separates them
			order = get_app_modules("frappe")
			self.assertLess(order.index(self.FIRST), order.index(self.SECOND))

			self.assertEqual(ship_dock_order([self.SECOND, self.FIRST]), get_app_modules("frappe"))

			order = get_app_modules("frappe")
			self.assertLess(order.index(self.SECOND), order.index(self.FIRST))

	def test_a_module_with_no_sidebar_gets_a_stub_rather_than_a_frozen_copy(self):
		"""Stating where a module sits must not also freeze what is in it. `mark_as_standard`
		ships the computed items on purpose; this ships the position and leaves the contents
		being computed, so the module keeps tracking its own contents afterwards."""
		with self.both_modules_on_disk(), developer_mode():
			self.assertFalse(frappe.db.exists("Module Sidebar", {"module": self.FIRST}))

			ship_dock_order([self.FIRST, self.SECOND])

			doc = frappe.get_doc("Module Sidebar", {"module": self.FIRST})
			self.assertEqual(doc.items, [], "shipping an order must not ship the module's contents")

			# ...and the module still renders the items its contents produce
			base = get_computed_base(self.FIRST)
			self.assertIn("Test Ship Order Alpha Report", [row.link_to for row in base.rows])

	def test_an_authored_sidebar_keeps_its_items(self):
		"""The other side of the same rule: a module that *does* ship its navigation gets a
		sequence written into the file it already has, and nothing else touched."""
		with self.both_modules_on_disk(), developer_mode():
			make_sidebar(self.FIRST)

			ship_dock_order([self.FIRST, self.SECOND])

			doc = frappe.get_doc("Module Sidebar", {"module": self.FIRST})
			self.assertEqual([row.link_to for row in doc.items], ["User"])
			self.assertEqual(doc.sequence_id, 1)

	def test_shipping_is_developer_mode_only(self):
		"""It writes files inside an app, which is the one thing developer mode gates."""
		with self.both_modules_on_disk(), no_developer_mode():
			self.assertRaises(frappe.ValidationError, ship_dock_order, [self.FIRST, self.SECOND])

	def test_re_shipping_renumbers_rather_than_accumulates(self):
		"""An order is the whole arrangement, not a delta, so shipping twice leaves the second
		one -- the same rule the layers above already run on."""
		with self.both_modules_on_disk(), developer_mode():
			ship_dock_order([self.FIRST, self.SECOND])
			ship_dock_order([self.SECOND, self.FIRST])

			self.assertEqual(self.sequence_of(self.SECOND), 1)
			self.assertEqual(self.sequence_of(self.FIRST), 2)

	def test_an_empty_order_is_refused(self):
		with developer_mode():
			self.assertRaises(frappe.ValidationError, ship_dock_order, [])

	def test_a_module_with_no_folder_is_refused_before_anything_is_written(self):
		"""Files are not in the transaction, so the check that would fail halfway has to run
		before the first write instead -- otherwise the rollback leaves the app holding the
		files for the modules that came first."""
		import os

		with module_resolvable_on_disk(self.FIRST), developer_mode():
			make_report(self.FIRST, "Test Ship Order Guard Report")
			clear_computed_base_cache(self.FIRST)
			self.addCleanup(frappe.db.delete, "Report", {"module": self.FIRST})

			# SECOND resolves to no folder, and it is named second
			self.assertRaises(frappe.ValidationError, ship_dock_order, [self.FIRST, self.SECOND])

			self.assertFalse(frappe.db.exists("Module Sidebar", {"module": self.FIRST}))
			self.assertFalse(
				os.path.exists(
					os.path.join(
						frappe.get_module_path(self.FIRST),
						"module_sidebar",
						frappe.scrub(self.FIRST),
					)
				),
				"a refused order still wrote a file into the app",
			)
