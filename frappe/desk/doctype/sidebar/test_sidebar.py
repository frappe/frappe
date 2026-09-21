# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.doctype.sidebar.sidebar import (
	ARRANGED_ITEM_FIELDS,
	COMPUTED_BASE_CACHE_KEY,
	MODULE_CONTENT_DOCTYPES,
	ROUTABLE_ENTITY_KINDS,
	SYSTEM_WRITE_FLAGS,
	UNROUTABLE_IN_A_TITLE,
	ShellIndex,
	build_canonical_shells,
	clear_computed_base_cache,
	filter_sidebar_items,
	get_app_sidebar_layer,
	get_computed_base,
	get_module_shell,
	get_sidebar,
	home_shell,
	item_key,
	mark_as_standard,
	reset_app_sidebar,
	routable_entities,
	routable_title,
	save_app_sidebar,
	shell_slug,
	unmark_as_standard,
)
from frappe.tests import IntegrationTestCase

MODULE = "Test Sidebar Module"


@contextmanager
def no_developer_mode():
	"""Create or delete a Module Def without touching the app on disk.

	In developer_mode a Module Def writes itself into the app's modules.txt and creates a folder on
	insert, but only undoes that on `after_commit`, which a rolled-back test never reaches, so the
	fixture would leak into the working tree.

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
	"""The system placing app content on a site, rather than a user authoring it.

	Each of these flags is set by a real route: an import, a fixture sync, a migrate, an app install
	or a patch. Each clears the developer-mode gate, since an app that ships a sidebar has to be
	installable on a customer site.

	"""
	original = frappe.flags.get(flag)
	frappe.flags[flag] = True
	try:
		yield
	finally:
		frappe.flags[flag] = original


@contextmanager
def sidebarless_module(name, app="frappe"):
	"""A `Module Def` with no `Sidebar`, which is the ordinary state since nothing writes one.

	It deliberately does not delete any `Sidebar` on the way in: `TestNothingWritesASidebar` asserts
	there is none, and a helper that swept first would hide the thing under test.

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
	"""Something for a computed base to be built from, in `module`.

	A Report, not a DocType: creating a DocType issues DDL, which commits, so the fixture would
	outlive the test's rollback and strand content on a module that no longer exists.

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
	"""Something in `module` that can be renamed, which a Report cannot be.

	`Page.validate` refuses any new page outside developer mode, including `standard: No`, and the
	test site does not have it on. Nothing is written to disk, because the export is gated on
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
	"""`Page.on_trash` refuses outside developer mode exactly as `validate` refuses the insert, so a
	page a test created has to be removed the way it was made.
	"""
	with developer_mode():
		frappe.delete_doc("Page", name, force=True, ignore_missing=True)


def make_sidebar(module: str, **kwargs):
	"""A `Sidebar` authored by hand, since nothing writes one on a module's behalf.

	It runs in developer mode because that is the only way one is authored: the document is app
	content, and on a customer site every one of them arrived by import.

	"""
	doc = frappe.new_doc("Sidebar")
	doc.module = module
	doc.update(kwargs)
	doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"})
	with developer_mode():
		return doc.insert(ignore_permissions=True)


@contextmanager
def module_resolvable_on_disk(module, app="frappe"):
	"""Make `module` resolve to a path, then undo it.

	`export_to_files` calls `get_module_path`, which resolves via `frappe.local.module_app`, built
	from the app's modules.txt. Registering the module in memory instead of writing that file keeps
	the working tree clean when the test rolls back.

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


def user_with_roles(email: str, roles: list[str]) -> str:
	"""A user holding exactly `roles` and nothing else.

	It is built rather than picked out of the test records, because a shared user carries whatever
	roles other suites needed, so a test claiming a user does not hold a role would really be
	asserting the state of the bench. Roles are reset on every call, since a previous run may have
	left some.

	"""
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)

	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in roles],
		}
	).insert(ignore_permissions=True)
	return email


class TestItemIdentity(IntegrationTestCase):
	"""What makes two sidebar rows the same item, and what that identity is made of.

	A linked row's four columns are its identity, so a rename repairs it. An unlinked row has
	nothing to repair and keeps a stored key. These tests pin both halves.

	"""

	def test_a_linked_row_is_identified_by_its_columns(self):
		"""No hash and no stored id: the value is the columns, which leaves the link column free to be
		repaired by an ordinary Dynamic Link rename.
		"""
		row = {"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"}

		self.assertEqual(item_key(row), "Link|DocType|User||")

	def test_identity_ignores_the_label_of_a_linked_row(self):
		"""Renaming an item in the sidebar must not orphan a user's delta."""
		self.assertEqual(
			item_key({"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"}),
			item_key({"type": "Link", "link_type": "DocType", "link_to": "User", "label": "People"}),
		)

	def test_a_filtered_row_is_a_different_item(self):
		"""The same doctype narrowed to a subset is somewhere else to go, not a second name for the
		same place. Without this the two share an identity and `filter_sidebar_items` keeps only the
		first -- which is how erpnext's Accounts sidebar lost "Credit Note" to "Sales Invoice".
		"""
		plain = {"type": "Link", "link_type": "DocType", "link_to": "Sales Invoice"}
		returns = {**plain, "filters": '{"is_return": 1}'}

		self.assertNotEqual(item_key(plain), item_key(returns))

	def test_both_survive_the_filter_that_drops_duplicates(self):
		"""The identity is only worth having if it reaches the pass that reads it."""
		rows = [
			frappe._dict(type="Link", link_type="DocType", link_to="User", label="Users", filters=None),
			frappe._dict(
				type="Link",
				link_type="DocType",
				link_to="User",
				label="Disabled Users",
				filters='{"enabled": 0}',
			),
		]

		kept = filter_sidebar_items(rows, None, check_permission=False)

		self.assertEqual([row["label"] for row in kept], ["Users", "Disabled Users"])

	def test_identity_follows_a_renamed_target(self):
		"""The other half: the identity does move when the target does, which is why base row and delta
		row, both rewritten by the rename, still match afterwards.
		"""
		before = item_key({"type": "Link", "link_type": "Report", "link_to": "Old Name"})
		after = item_key({"type": "Link", "link_type": "Report", "link_to": "New Name"})

		self.assertNotEqual(before, after)

	def test_a_stored_key_never_beats_a_link(self):
		"""A key stored beside the columns could only be a staler second answer: it would survive a
		rename still naming what the row used to point at.
		"""
		row = {"type": "Link", "link_type": "DocType", "link_to": "User", "key": "stale-0"}

		self.assertEqual(item_key(row), item_key({k: v for k, v in row.items() if k != "key"}))

	def test_unlinked_rows_are_told_apart_by_their_label(self):
		"""Every Section Break used to collide, which is what the ordinal was for. Including the label
		removes the collision instead, and with it the ordinal, which re-anchored every delta below
		an insertion.
		"""
		sections = [{"type": "Section Break", "label": f"S{i}"} for i in range(4)]

		self.assertEqual(len({item_key(row) for row in sections}), 4)

	def test_an_unlinked_row_keeps_a_stored_key(self):
		"""It is how a customization row names a Section Break: there are no link columns to name it
		by, and its label is a field the customization may itself override.
		"""
		row = {"type": "Section Break", "label": "Reports", "key": "abc1234567"}

		self.assertEqual(item_key(row), "abc1234567")

	def test_the_key_assignment_pass_is_gone(self):
		"""Identity is derived from columns the row already carries, so nothing writes a key into a
		base row on save, and nothing re-keys one on re-authoring.
		"""
		from frappe.desk.doctype.sidebar import sidebar

		for retired in ("derive_key", "assign_keys", "boot_dedupe_key", "BOOT_DEDUPE_FIELDS"):
			self.assertFalse(hasattr(sidebar, retired), f"{retired} should have been deleted")

		self.assertFalse(hasattr(frappe.new_doc("Sidebar"), "validate_unique_keys"))

	def test_a_base_row_stores_no_key_at_all(self):
		"""There is nothing to keep in step with the columns, so nothing is written. A key an older
		derivation left behind is cleared rather than used, so the same section is identified the
		same way on an upgraded site and a fresh one.
		"""
		with sidebarless_module("Test Unkeyed Rows Module") as module:
			doc = make_sidebar(module)
			doc.append("items", {"type": "Section Break", "label": "Reports", "key": "9f8e7d6c5b-2"})
			with developer_mode():
				doc.save(ignore_permissions=True)

			self.assertEqual([row.key for row in doc.items], [None, None])
			self.assertEqual(item_key(doc.items[1]), item_key({"type": "Section Break", "label": "Reports"}))

	def test_boot_does_not_read_a_stale_key_off_a_base_row(self):
		"""Clearing on save retires them as each app re-imports its sidebar. Until then the rows are
		still in the database, and the resolution must not pick them up.
		"""
		from frappe.desk.doctype.sidebar.sidebar import get_sidebar_bases

		with sidebarless_module("Test Stale Key Module") as module:
			doc = make_sidebar(module)
			# behind `validate`'s back, the way a row written by the old derivation still looks
			frappe.db.set_value(
				"Sidebar Item", doc.items[0].name, "key", "9f8e7d6c5b-0", update_modified=False
			)

			base = get_sidebar_bases([module])[module]

			self.assertIsNone(base.rows[0].get("key"))
			self.assertEqual(item_key(base.rows[0]), "Link|DocType|User||")


class TestSidebarDocument(IntegrationTestCase):
	"""A `Sidebar` is app content: authored in developer mode, backed by a file when standard, and
	owned by its module for as long as the module exists.
	"""

	def setUp(self):
		if not frappe.db.exists("Module Def", MODULE):
			with no_developer_mode():
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": MODULE, "app_name": "frappe"}
				).insert()

	def tearDown(self):
		# `delete_doc`, not `db.delete`: the latter leaves the item rows behind, and since a
		# sidebar is named after its module the next one to be inserted adopts the orphans
		for name in frappe.get_all("Sidebar", filters={"module": MODULE}, pluck="name"):
			frappe.delete_doc("Sidebar", name, force=True, ignore_permissions=True)
		with no_developer_mode():
			frappe.delete_doc("Module Def", MODULE, force=True, ignore_missing=True)

	def link(self, doctype, label=None):
		return {"type": "Link", "link_type": "DocType", "link_to": doctype, "label": label or doctype}

	def test_a_site_owned_row_cannot_be_made_standard_by_hand(self):
		"""`standard` means backed by a file. Setting it without writing one leaves a row that orphan
		removal deletes on the next migrate, so validate refuses it.
		"""
		doc = make_sidebar(MODULE)
		self.assertEqual(doc.standard, 0)
		with self.assertRaises(frappe.ValidationError):
			doc.standard = 1
			doc.save()

	def test_site_owned_row_survives_orphan_removal(self):
		"""Orphan removal only considers standard rows. A site-owned sidebar has no file by
		definition and must never be mistaken for one whose file went missing.
		"""
		from frappe.model.sync import remove_orphan_entities

		make_sidebar(MODULE)
		remove_orphan_entities("Sidebar")
		self.assertTrue(frappe.db.exists("Sidebar", MODULE))

	def test_deleting_the_module_removes_its_sidebar(self):
		make_sidebar(MODULE)
		frappe.delete_doc("Module Def", MODULE, force=True)
		self.assertFalse(frappe.db.exists("Sidebar", MODULE))

	def test_items_may_come_from_any_module(self):
		"""A sidebar's items are deliberately not constrained to its module.

		Authors group by what belongs together in navigation, which is not the same as what a module
		owns. That flexibility is why splitting a module later needs no tooling. This is pinned so
		nobody adds a well-meaning validation.

		"""
		sidebar = frappe.new_doc("Sidebar")
		sidebar.module = MODULE
		# User is Core, Report is Core and Workspace is Desk, so none of them is this module.
		for item in (self.link("User"), self.link("Report"), self.link("DocType")):
			sidebar.append("items", item)
		# Authored by hand, so in developer mode: the document is app content.
		with developer_mode():
			sidebar.insert(ignore_permissions=True)

		self.assertEqual(len(frappe.get_doc("Sidebar", MODULE).items), 3)

	def test_identities_survive_export_and_reimport(self):
		"""Export to JSON, re-import twice, and assert the deltas would still resolve.

		This is the property item identity exists for. `import_doc` deletes and re-inserts, and child
		rows are hash-named, so every re-import produces different row names. A customization anchored
		on `name` would break on every `bench migrate`. Anchored on the row's own columns it survives,
		because nothing about them is generated.

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

			path = os.path.join(module_path, "sidebar", scrubbed, f"{scrubbed}.json")
			self.assertTrue(os.path.exists(path), f"export did not write {path}")

			for _ in range(2):
				import_file_by_path(path, force=True, ignore_version=True)

			after_doc = frappe.get_doc("Sidebar", MODULE)
			after = {item_key(i): i.link_to for i in after_doc.items}
			names_after = {i.name for i in after_doc.items}

		self.assertEqual(before, after, "identities must be identical across re-import")
		self.assertNotEqual(names_before, names_after, "sanity: child row names are regenerated")


class TestSidebarIsNamedByItsTitle(IntegrationTestCase):
	"""A sidebar's record name is its title, and the title defaults to its module's name.

	The default is what makes this cheap: every sidebar shipped today is titled after its module, so
	storing the default leaves their record names, exported paths and references unchanged. What it
	buys is a module that owns more than one sidebar, such as Leads and Deals both under `FCRM`,
	which `unique` on `module` made impossible.

	"""

	MODULE = "Test Sidebar Naming Module"
	DEALS = "Test Sidebar Deals"
	LEADS = "Test Sidebar Leads"
	RENAMED = "Test Sidebar Renamed"

	def setUp(self):
		with no_developer_mode():
			frappe.get_doc(
				{"doctype": "Module Def", "module_name": self.MODULE, "app_name": "frappe"}
			).insert()

	def tearDown(self):
		for name in frappe.get_all("Sidebar", filters={"module": self.MODULE}, pluck="name"):
			frappe.delete_doc("Sidebar", name, force=True, ignore_permissions=True)
		with no_developer_mode():
			frappe.delete_doc("Module Def", self.MODULE, force=True, ignore_missing=True)

	def test_the_record_is_named_by_its_title(self):
		self.assertEqual(make_sidebar(self.MODULE, title=self.DEALS).name, self.DEALS)

	def test_the_title_defaults_to_the_module_and_is_stored(self):
		"""Stored rather than computed on read, which is why the ten sidebars frappe ships with
		`title == module` keep the names they already had.
		"""
		doc = make_sidebar(self.MODULE)
		self.assertEqual(doc.name, self.MODULE)
		self.assertEqual(frappe.db.get_value("Sidebar", doc.name, "title"), self.MODULE)

	def test_two_sidebars_may_share_one_module(self):
		"""The point of the change. `Sidebar.module` was `unique`, so a module got exactly one
		sidebar forever."""
		leads = make_sidebar(self.MODULE, title=self.LEADS)
		deals = make_sidebar(self.MODULE, title=self.DEALS)

		self.assertEqual(
			sorted(frappe.get_all("Sidebar", filters={"module": self.MODULE}, pluck="name")),
			sorted([leads.name, deals.name]),
		)

	def test_two_sidebars_may_not_share_a_title(self):
		"""What a name is: the one thing two sidebars cannot both have. It is refused by the primary
		key, since a sidebar's name is its title.
		"""
		make_sidebar(self.MODULE, title=self.LEADS)

		# postgres aborts the transaction on a failed statement, so recover to a savepoint
		frappe.db.savepoint("duplicate_title")
		with self.assertRaises(frappe.DuplicateEntryError):
			make_sidebar(self.MODULE, title=self.LEADS)
		frappe.db.rollback(save_point="duplicate_title")

	def test_the_title_index_catches_a_row_whose_name_has_drifted(self):
		"""What `unique` on `title` buys over the primary key, which already forbids two records of
		one name.

		A row written straight to the table, such as a legacy row or a raw update that skips
		`_sync_autoname_field`, can carry a title its name does not match. The index refuses to let a
		second sidebar claim that title, and nothing else would.

		"""
		drifted = make_sidebar(self.MODULE)
		frappe.db.set_value("Sidebar", drifted.name, "title", self.LEADS, update_modified=False)

		frappe.db.savepoint("drifted_title")
		with self.assertRaises(frappe.UniqueValidationError):
			make_sidebar(self.MODULE, title=self.LEADS)
		frappe.db.rollback(save_point="drifted_title")

	def test_module_is_neither_required_nor_unique(self):
		module = frappe.get_meta("Sidebar").get_field("module")
		self.assertFalse(module.reqd)
		self.assertFalse(module.unique)

	def test_no_index_replaces_the_dropped_unique(self):
		"""`unique: 1` was silently indexing `module`, and nothing takes its place. Neither
		`Custom Sidebar.module` nor `Workspace.module` declares one, and `Custom Sidebar` runs the
		same access pattern on a larger table.
		"""
		self.assertFalse(frappe.get_meta("Sidebar").get_field("module").search_index)
		self.assertFalse(hasattr(frappe.new_doc("Sidebar"), "on_doctype_update"))

	def test_a_module_lands_on_the_sidebar_named_after_it(self):
		"""The naming rule, and why no `is_default` column is needed: which of a module's sidebars
		answers for the module is decided by what it is called.
		"""
		make_sidebar(self.MODULE, title=self.DEALS)
		own = make_sidebar(self.MODULE)

		self.assertEqual(get_sidebar(self.MODULE).name, own.name)

	def test_a_module_named_by_none_of_its_sidebars_falls_back_to_the_computed_base(self):
		"""The other half of the rule. A sidebar under this module but called something else is a
		second shell, reached by a dock row naming it, not the module's own.
		"""
		make_sidebar(self.MODULE, title=self.DEALS)

		self.assertIsNone(get_sidebar(self.MODULE))

	def test_editing_the_title_renames_the_record(self):
		"""`field:` autoname only runs on insert, and `_sync_autoname_field` copies the name back over
		the column on every save, so without the rename the edit would silently revert.
		"""
		doc = make_sidebar(self.MODULE)
		with developer_mode():
			doc.title = self.RENAMED
			doc.save(ignore_permissions=True)

		self.assertEqual(doc.name, self.RENAMED)
		self.assertFalse(frappe.db.exists("Sidebar", self.MODULE))
		self.assertEqual(frappe.db.get_value("Sidebar", self.RENAMED, "title"), self.RENAMED)
		self.assertEqual(len(frappe.get_doc("Sidebar", self.RENAMED).items), 1, "its items came too")

	def test_an_import_is_named_by_its_file_rather_than_renamed(self):
		"""A file carries its own `name`, and that name is the record's identity. A file whose `title`
		disagrees with it is saying two things, and an app shipping one must not have its row moved,
		or its folder deleted, mid-import.
		"""
		doc = make_sidebar(self.MODULE)

		with system_write(), no_developer_mode():
			doc.title = self.RENAMED
			doc.save(ignore_permissions=True)

		self.assertEqual(doc.name, self.MODULE, "the file's name still says which record this is")
		self.assertEqual(frappe.db.get_value("Sidebar", self.MODULE, "title"), self.MODULE)
		self.assertFalse(frappe.db.exists("Sidebar", self.RENAMED))

	def test_a_dock_row_naming_the_shell_follows_the_rename(self):
		"""A dock row naming a shell is a `Sidebar` link, and a rename has to carry onto it, or the
		row would point at a sidebar that no longer answers. `rename_sidebar_rows` moves the row and
		drops the caches the layer is read from; `rename_dynamic_links` may have moved it first,
		which is why that pass looks the row up under both names.
		"""
		doc = make_sidebar(self.MODULE)
		# one `Dock` per app per person, enforced by a unique index, so whatever this site holds
		# at that address goes first
		frappe.db.delete("Dock", {"app": "frappe", "user": "test@example.com"})
		layer = frappe.get_doc(
			{
				"doctype": "Dock",
				"app": "frappe",
				"user": "test@example.com",
				"items": [{"link_type": "Sidebar", "link_to": self.MODULE}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Dock", layer.name, force=True, ignore_permissions=True)

		with developer_mode():
			doc.title = self.RENAMED
			doc.save(ignore_permissions=True)

		self.assertEqual(frappe.get_doc("Dock", layer.name).items[0].link_to, self.RENAMED)

	def test_deleting_the_module_deletes_every_sidebar_it_owns(self):
		"""Deleting by name reached exactly one, which was every one of them while a module
		could only have one."""
		make_sidebar(self.MODULE)
		make_sidebar(self.MODULE, title=self.DEALS)

		frappe.delete_doc("Module Def", self.MODULE, force=True)

		self.assertEqual(frappe.get_all("Sidebar", filters={"module": self.MODULE}), [])

	def test_the_sidebars_frappe_ships_are_all_named_by_their_titles(self):
		"""All eleven are titled after the module that owns them, so naming by title moves nothing: a
		shipped sidebar's record name, title and module are one string, and its exported path follows
		that module's folder.
		"""
		import os

		shipped = frappe.get_all(
			"Sidebar", filters={"standard": 1, "app": "frappe"}, fields=["name", "module", "title"]
		)
		self.assertEqual([row.name for row in shipped if row.name != row.module], [])
		for row in shipped:
			self.assertEqual(row.name, row.title)

		self.assertEqual(
			frappe.get_doc("Sidebar", "Build").exported_file_path(),
			os.path.join(frappe.get_module_path("Build"), "sidebar", "build", "build.json"),
		)


class TestSidebarTitleIsRoutable(IntegrationTestCase):
	"""A sidebar's name is a segment of the desk URL, so it has to survive being one.

	`/desk/stock/item` names the Stock shell and the Item list. The name reaches the URL through
	`frappe.router.slug`, which only lowercases and turns spaces into dashes, so anything else in
	the title lands in the path as it was written.

	The rule is only about characters a path cannot carry. It says nothing about the module: a
	module may still own several sidebars, and the second one is a shell with a URL of its own.
	"""

	MODULE = "Test Sidebar Routing Module"
	SECOND = "Test Sidebar Second Shell"

	def setUp(self):
		with no_developer_mode():
			frappe.get_doc(
				{"doctype": "Module Def", "module_name": self.MODULE, "app_name": "frappe"}
			).insert()

	def tearDown(self):
		for name in frappe.get_all("Sidebar", filters={"module": self.MODULE}, pluck="name"):
			frappe.delete_doc("Sidebar", name, force=True, ignore_permissions=True)
		with no_developer_mode():
			frappe.delete_doc("Module Def", self.MODULE, force=True, ignore_missing=True)

	def test_a_title_the_url_cannot_carry_is_refused(self):
		"""One case per character, because each breaks the path differently: `/` ends the segment,
		`?` and `#` end the path, `%` opens an escape, and `\\` is a separator to some servers.
		"""
		for title in ("Pay/Benefits", "Why?", "100% Club", "A#B", "C\\D"):
			with self.subTest(title=title):
				# postgres aborts the transaction on a failed statement, so recover to a savepoint
				frappe.db.savepoint("unroutable_title")
				with self.assertRaises(frappe.ValidationError):
					make_sidebar(self.MODULE, title=title)
				frappe.db.rollback(save_point="unroutable_title")

	def test_an_ampersand_is_allowed_because_the_slug_spells_it_out(self):
		"""hrms named two shells with an `&` on purpose, since a module folder is a Python package
		and cannot hold one. `&` is legal in a path, so the name stands and the slug is what
		turns it into `shift-and-attendance`.
		"""
		self.assertEqual(make_sidebar(self.MODULE, title="Shift & Attendance").name, "Shift & Attendance")

	def test_a_title_in_another_script_is_allowed(self):
		"""Non-ASCII percent-encodes, round-trips, and a browser shows it as it was written.
		Refusing it would say a shell can only be named in English.
		"""
		self.assertEqual(make_sidebar(self.MODULE, title="कर्मचारी").name, "कर्मचारी")

	def test_a_second_shell_under_one_module_keeps_its_own_name(self):
		"""The rule is about the URL, not the module.

		This is here to catch a tightening that would tie the title back to its module. That would
		read as tidier, and it would delete the second shell, since two sidebars cannot share a
		title. A second shell now has a URL of its own, which is the reason to keep it.
		"""
		own = make_sidebar(self.MODULE)
		second = make_sidebar(self.MODULE, title=self.SECOND)

		self.assertEqual(second.module, own.module)
		self.assertEqual(own.name, self.MODULE)
		self.assertEqual(second.name, self.SECOND)

	def test_a_title_that_slugs_like_another_shell_is_refused(self):
		"""The desk keys shells by slug, and the second one written wins. Two titles that differ
		only in case, the spelling of `&` or their spacing reach it as one segment, and one of
		them would have no URL at all.
		"""
		make_sidebar(self.MODULE, title="Pay & Benefits")

		for title in ("Pay and Benefits", "pay & benefits", "Pay  &  Benefits"):
			with self.subTest(title=title):
				frappe.db.savepoint("colliding_title")
				with self.assertRaises(frappe.ValidationError):
					make_sidebar(self.MODULE, title=title)
				frappe.db.rollback(save_point="colliding_title")

	def test_a_title_that_slugs_like_a_bare_module_is_refused(self):
		"""A module with no sidebar document still gets a computed shell under its own name, and
		that name is a segment too.

		Spelled with `&` against a module spelled with `and`, so the titles are different strings
		and `validate_title_is_its_own` -- which refuses another module's exact name -- has
		nothing to say. Only the slug catches it.
		"""
		bare = "Test Sidebar Bare and Module"
		with no_developer_mode():
			frappe.get_doc({"doctype": "Module Def", "module_name": bare, "app_name": "frappe"}).insert()
		self.addCleanup(self.drop_module, bare)

		with self.assertRaises(frappe.ValidationError):
			make_sidebar(self.MODULE, title="Test Sidebar Bare & Module")

	def test_a_sidebar_may_slug_like_its_own_module(self):
		"""hrms titles the sidebar of module `Shift and Attendance` as `Shift & Attendance`. Both
		slug to one segment, and that is fine: a module whose sidebar has a document gets no
		computed shell of its own, so only one of the two is ever a shell.
		"""
		title = self.MODULE.replace(" ", " & ", 1)
		module = self.MODULE.replace(" ", " and ", 1)
		with no_developer_mode():
			frappe.get_doc({"doctype": "Module Def", "module_name": module, "app_name": "frappe"}).insert()
		self.addCleanup(self.drop_module, module)

		self.assertEqual(make_sidebar(module, title=title).name, title)

	def test_renaming_a_sidebar_to_its_own_slug_is_allowed(self):
		"""Changing only the case or the spacing of a title leaves its segment where it was, and
		it must not collide with itself.
		"""
		doc = make_sidebar(self.MODULE, title=self.SECOND)
		doc.title = self.SECOND.lower()
		with developer_mode():
			doc.save(ignore_permissions=True)

	def test_an_old_title_is_repaired_rather_than_refused(self):
		"""What the v16 conversion does with a title from before the rule. The characters a path
		cannot carry become spaces, so the author's words survive, and a title that still takes
		another shell's URL falls back to the module.
		"""
		self.assertEqual(routable_title("Pay/Benefits", self.MODULE), "Pay Benefits")
		self.assertEqual(routable_title("100% Club?", self.MODULE), "100 Club")

		make_sidebar(self.MODULE, title="Taken Title")
		self.assertEqual(routable_title("Taken/Title", self.MODULE), self.MODULE)

	def test_an_old_title_is_numbered_when_the_module_name_is_taken_too(self):
		"""Another module's sidebar can already answer to this module's slug, as `Shift and
		Attendance` does for a module `Shift & Attendance`. Handing back the module's name then
		would only have `insert` refuse it and abort the migrate, so it is numbered instead.
		"""
		taken = {shell_slug("Taken Title"), shell_slug(self.MODULE)}
		with patch(
			"frappe.desk.doctype.sidebar.sidebar.shell_holding_slug",
			side_effect=lambda title, **kwargs: "Other" if shell_slug(title) in taken else None,
		):
			self.assertEqual(routable_title("Taken/Title", self.MODULE), f"{self.MODULE} 2")

			taken.add(shell_slug(f"{self.MODULE} 2"))
			self.assertEqual(routable_title("Taken/Title", self.MODULE), f"{self.MODULE} 3")

	@staticmethod
	def drop_module(module):
		for name in frappe.get_all("Sidebar", filters={"module": module}, pluck="name"):
			frappe.delete_doc("Sidebar", name, force=True, ignore_permissions=True)
		with no_developer_mode():
			frappe.delete_doc("Module Def", module, force=True, ignore_missing=True)

	def test_the_sidebars_frappe_ships_all_survive_a_url(self):
		for name in frappe.get_all("Sidebar", filters={"standard": 1, "app": "frappe"}, pluck="name"):
			with self.subTest(name=name):
				self.assertEqual([c for c in UNROUTABLE_IN_A_TITLE if c in name], [])


def shell_payload(spec: dict) -> dict:
	"""A `bootinfo.module_sidebars` payload from a compact spelling, for the ladder's tests.

	Each shell is given as `{"module": ..., "workspaces": [...], "lists": [(kind, entity), ...]}`,
	and everything the ladder does not read is left out. Building the payload by hand rather than
	from documents is what lets one test say one thing: the ladder's order is the subject, and
	real sidebars would drag permissions, customizations and computed bases into it.
	"""
	return {
		shell: {
			"module": shell_spec.get("module", shell),
			"workspaces": shell_spec.get("workspaces", []),
			"computed": shell_spec.get("computed", 0),
			"items": [{"link_type": kind, "link_to": entity} for kind, entity in shell_spec.get("lists", [])],
		}
		for shell, shell_spec in spec.items()
	}


class TestCanonicalShell(IntegrationTestCase):
	"""Where an entity opens when nothing else states a shell.

	This is the desk's resolution ladder minus its two per-browser inputs, so what is left can be
	worked out on the server and reads the same on every device. The tests below are the ladder's
	steps, one each, in the order they run.
	"""

	def test_the_entitys_own_module_answers_when_its_shell_lists_it(self):
		index = shell_payload({"Stock": {"lists": [("DocType", "Item")]}, "Selling": {}})

		self.assertEqual(ShellIndex(index).resolve("DocType", "Item", "Stock"), "Stock")

	def test_a_shell_listing_the_entity_beats_a_module_that_does_not(self):
		"""The step that must not be dropped.

		It reads as redundant beside the last one, since a module usually has a shell of its own,
		and removing it moved a hundred entities on an erpnext and hrms site. `Appraisal` is the
		shape of it: its module is `HR`, `HR` has a shell, and hrms split its navigation out so
		`Performance` is what lists it. Without this step every such entity lands back in the
		module the split exists to empty.
		"""
		index = shell_payload({"HR": {}, "Performance": {"lists": [("DocType", "Appraisal")]}})

		self.assertEqual(ShellIndex(index).resolve("DocType", "Appraisal", "HR"), "Performance")

	def test_a_computed_sidebar_keeps_its_module_s_entities_anyway(self):
		"""Not listing something only says something when someone chose what the sidebar lists.

		A computed sidebar lists what its module holds, capped at a display limit, so an entity
		missing from one was not left out. Reading that as a decision hands the entity to whichever
		other shell happens to link it. This is the case for every module a customer adds, since
		nobody shipped a sidebar for it, and a site whose apps all ship one has no computed shells
		at all -- which is why leaving this out looks harmless.
		"""
		index = shell_payload(
			{
				"Widgets": {"computed": 1},
				"Selling": {"lists": [("DocType", "Widget")]},
			}
		)

		self.assertEqual(ShellIndex(index).resolve("DocType", "Widget", "Widgets"), "Widgets")

	def test_a_shipped_sidebar_that_omits_the_entity_gives_it_away(self):
		"""The other half. An app wrote this sidebar and left the entity out, so that is a
		decision, and a shell that does list it wins.
		"""
		index = shell_payload(
			{
				"Widgets": {"computed": 0},
				"Selling": {"lists": [("DocType", "Widget")]},
			}
		)

		self.assertEqual(ShellIndex(index).resolve("DocType", "Widget", "Widgets"), "Selling")

	def test_the_module_answers_last_when_no_shell_lists_the_entity(self):
		index = shell_payload({"Stock": {}, "Selling": {"lists": [("DocType", "Customer")]}})

		self.assertEqual(ShellIndex(index).resolve("DocType", "Warehouse", "Stock"), "Stock")

	def test_an_heir_that_lists_the_entity_answers_for_a_code_only_module(self):
		"""`Core` ships no navigation and declares where it went. The heir that lists the entity
		wins over the first heir declared, which is how `User` reaches `Users` rather than
		`System`.
		"""
		index = shell_payload({"System": {}, "Build": {}, "Users": {"lists": [("DocType", "User")]}})

		self.assertEqual(ShellIndex(index).resolve("DocType", "User", "Core"), "Users")

	def test_the_first_heir_takes_what_none_of_them_lists(self):
		"""`Core`'s heirs are declared `System, Build, Data, Users, Email`, and `System` leads on
		purpose: it is the internals shell, so an unplaced `Core` doctype lands there rather than
		turning the developer-tooling sidebar into the dumping ground.
		"""
		index = shell_payload({"Build": {}, "System": {}, "Users": {}})

		self.assertEqual(ShellIndex(index).resolve("DocType", "Tag Link", "Core"), "System")

	def test_a_module_with_no_shell_and_no_heirs_answers_nothing(self):
		index = shell_payload({"Stock": {}})

		self.assertIsNone(ShellIndex(index).resolve("DocType", "Widget", "Some Vanished Module"))

	def test_a_renamed_shell_still_answers_for_its_module(self):
		"""A sidebar's name and its module are two different things, so the module is found
		through the column the shell stores it in, not by assuming the two agree.
		"""
		index = shell_payload(
			{"Quality": {"module": "Quality Management", "lists": [("DocType", "Quality Goal")]}}
		)

		self.assertEqual(
			ShellIndex(index).resolve("DocType", "Quality Goal", "Quality Management"), "Quality"
		)

	def test_a_name_shared_across_kinds_resolves_apart(self):
		"""Entity names are not unique across kinds. On an erpnext and hrms site `Attendance` is
		both a DocType in `HR` and a Dashboard in `Shift & Attendance`, and `Project`, `Selling`
		and `Stock` each name both a Dashboard and a doctype. A flat map answers one of each pair
		wrong, whichever order it was built in.
		"""
		index = ShellIndex(
			shell_payload(
				{
					"HR": {"lists": [("DocType", "Attendance")]},
					"Shift & Attendance": {"lists": [("Dashboard", "Attendance")]},
				}
			)
		)

		self.assertEqual(index.resolve("DocType", "Attendance", "HR"), "HR")
		self.assertEqual(index.resolve("Dashboard", "Attendance", "HR"), "Shift & Attendance")

	def test_a_workspace_belongs_to_the_shell_that_lists_it(self):
		"""Workspaces skip the ladder. Which shell a workspace belongs to is stored on the shell,
		so there is nothing to resolve.
		"""
		index = ShellIndex(shell_payload({"Stock": {"workspaces": ["Stock", "Warehousing"]}}))

		self.assertEqual(dict(index.workspace_owners()), {"Stock": "Stock", "Warehousing": "Stock"})


class TestCanonicalShellPayload(IntegrationTestCase):
	"""The whole map, against the site as it stands."""

	@staticmethod
	def build(with_home=False):
		from frappe.boot import build_entity_module_map, get_module_sidebars
		from frappe.desk.desk_views import DeskViews

		desk_views = DeskViews()
		desk_views.build_entities()
		sidebars = get_module_sidebars()
		canonical, home = build_canonical_shells(sidebars, build_entity_module_map(sidebars), desk_views)
		if with_home:
			return canonical, home, routable_entities(desk_views)
		return canonical

	def assert_total(self):
		"""Everything the user can reach is in the map. Compared against what they can reach
		rather than read off the map itself, because the map leaves out what it could not place,
		so checking its own values for a missing shell finds nothing by construction.
		"""
		canonical, home, reachable = self.build(with_home=True)

		self.assertTrue(reachable["DocType"], "the user can read nothing, so this test proves nothing")
		for kind, entities in reachable.items():
			self.assertEqual(sorted(set(entities) - set(canonical[kind])), [], kind)
		return canonical, home

	def test_every_doctype_the_user_can_read_lands_somewhere(self):
		"""The ladder has to be total. A doctype with no shell has no prefix to put in its URL,
		so it would be the one route shaped differently from every other.
		"""
		self.assert_total()

	def test_a_user_with_most_modules_blocked_still_lands_everywhere(self):
		"""The case the map used to miss. Administrator sees every module, so every step of the
		ladder has a shell to answer with, and the map was complete for the user it was built
		and tested as. A user who may see one module can still read doctypes from all the others,
		and before the last two steps those opened with no sidebar. On erpnext.site it was 135
		of 151 doctypes for a Selling-only user.
		"""
		from frappe.boot import get_module_sidebars

		frappe.set_user("Administrator")
		kept = next(iter(get_module_sidebars()))
		blocked = [m for m in frappe.get_all("Module Def", pluck="name") if m != kept]
		email = user_with_roles("test-sidebar-one-module@example.com", ["System Manager"])
		user = frappe.get_doc("User", email)
		user.set("block_modules", [{"module": module} for module in blocked])
		user.save(ignore_permissions=True)
		self.enterContext(self.set_user(email))

		shells = set(get_module_sidebars())
		canonical, home = self.assert_total()

		self.assertIn(home, shells)
		named = {shell for found in canonical.values() for shell in found.values()}
		self.assertEqual(named - shells, set())

	def test_workspaces_are_not_in_the_shipped_map(self):
		"""The desk answers a workspace from `module_sidebars[shell].workspaces`, which it already
		has. A second copy in the map is payload nothing reads, and two copies of one fact can
		disagree. `home_shell` still needs the answer, and gets it without shipping it.
		"""
		self.assertEqual(sorted(self.build()), sorted(ROUTABLE_ENTITY_KINDS))
		self.assertNotIn("Workspace", self.build())

	def test_every_shell_named_is_one_the_user_can_see(self):
		"""The map is built from an already-filtered payload, so it can only name a shell this
		user has. A name outside it would be a shell the desk cannot render.
		"""
		from frappe.boot import get_module_sidebars

		shells = set(get_module_sidebars())
		named = {shell for found in self.build().values() for shell in found.values()}

		self.assertEqual(named - shells, set())

	def test_home_is_where_most_of_the_work_is(self):
		"""Not the shell that sorts first. For a user whose shells are `Custom Workspaces` and
		`Selling`, the first is a place to keep their own pages, and Selling is where they work.
		"""
		sidebars = {"Custom Workspaces": {}, "Selling": {}}
		canonical = {"DocType": {"Customer": "Selling", "Quotation": "Selling", "Note": "Custom Workspaces"}}
		workspaces = {"Mine": "Custom Workspaces", "Other": "Custom Workspaces"}

		self.assertEqual(home_shell(sidebars, canonical, workspaces, default_workspace=None), "Selling")

	def test_home_ties_go_to_the_earlier_shell(self):
		self.assertEqual(home_shell({"A": {}, "B": {}}, {"DocType": {}}, {}), "A")

	def test_home_is_the_shell_of_the_users_default_workspace(self):
		"""What the user asked for beats where the ladder put the most of their work. The desk
		used to settle this for itself, off `boot.user.default_workspace`; it reads the answer
		as `boot.home_shell` now, so this is the only place the choice is honoured.
		"""
		sidebars = {"Custom Workspaces": {}, "Selling": {}}
		canonical = {"DocType": {"Customer": "Selling", "Quotation": "Selling"}}

		self.assertEqual(
			home_shell(sidebars, canonical, {"Mine": "Custom Workspaces"}, default_workspace="Mine"),
			"Custom Workspaces",
		)

	def test_a_default_workspace_the_user_cannot_see_is_ignored(self):
		"""A workspace absent from the map is one this user cannot reach, so landing them on it
		would land them on nothing. The count decides instead, as it does for a user who set no
		default at all.
		"""
		sidebars = {"Custom Workspaces": {}, "Selling": {}}
		canonical = {"DocType": {"Customer": "Selling"}}

		self.assertEqual(home_shell(sidebars, canonical, {}, default_workspace="Gone"), "Selling")

	def test_the_boot_hands_over_the_default_it_already_loaded(self):
		"""`get_user` reads the default workspace before `load_desktop_data` runs, and the boot
		passes that value on rather than reading it again. Checked through the boot itself,
		because the wiring between the two is the part that can break.

		The workspace is picked from a shell the count would not choose, so the answer can only
		come from the default.
		"""
		from frappe.boot import load_desktop_data

		without = frappe._dict(user=frappe._dict(default_workspace=None))
		load_desktop_data(without)

		# Read through the same index the boot uses, since a workspace two shells list belongs to
		# the first of them and not to whichever this loop happens to meet.
		owners = ShellIndex(without.module_sidebars).workspace_owners()
		elsewhere = next(((ws, shell) for ws, shell in owners if shell != without.home_shell), None)
		if not elsewhere:
			self.skipTest("every workspace on this site sits in the home shell")

		workspace, shell = elsewhere
		chosen = frappe._dict(user=frappe._dict(default_workspace={"name": workspace}))
		load_desktop_data(chosen)

		self.assertEqual(chosen.home_shell, shell)

	def test_child_tables_are_absent(self):
		"""A child table is never routed to, so carrying one would only make the payload bigger."""
		canonical = self.build()
		tables = frappe.get_all("DocType", filters={"istable": 1}, pluck="name", limit=200)

		self.assertEqual([name for name in tables if name in canonical["DocType"]], [])


class TestSidebarStandard(IntegrationTestCase):
	"""`standard` is the export switch, and marking flips it by writing the file.

	Marking a module's sidebar standard builds a document and exports it. It takes the base the
	module already has, computed from its contents when no app shipped one, writes it as a document
	and exports it, so an author starts from what the desk shows rather than from nothing. Un-marking
	deletes the document, which returns the module to that computed base in the same request.

	The file is the point. `standard` means backed by a JSON file in an app, and orphan removal
	deletes a standard record whose file is missing, so a half-done mark is a row that deletes itself
	on the next migrate.

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

		It runs at both ends, because the commit in `tearDown` puts this suite's fixtures beyond the
		framework's rollback: a Report left behind points at a module that no longer exists and turns
		up in the next test's computed base.

		It uses `delete_doc` rather than `frappe.db.delete`: the sidebar is named after its module, so
		item rows left behind by a raw delete would be inherited by the next document of the same name.

		"""
		for name in frappe.get_all("Sidebar", filters={"module": MODULE}, pluck="name"):
			frappe.delete_doc("Sidebar", name, force=True, ignore_permissions=True)
		frappe.db.delete("Report", {"module": MODULE})

	def with_content(self):
		"""Something for the module's computed base to be built out of."""
		make_report(MODULE, "Test Standard Sidebar Report")
		clear_computed_base_cache(MODULE)

	def exported_json(self, path):
		"""The exported file, minus what the framework stamps on every write.

		Two exports of the same sidebar differ only in their timestamps, so the comparison has to drop
		them to say anything about the content.

		"""
		with open(path) as f:
			content = json.load(f)
		for field in ("creation", "modified", "modified_by", "owner", "docstatus", "idx"):
			content.pop(field, None)
		return content

	def test_marking_a_module_with_no_document_ships_its_computed_base(self):
		"""The build half. Nothing persists a base, so the ordinary state of a module is to have no
		document, and marking it standard has to produce one from what the desk is already rendering
		rather than an empty shell to fill in by hand.
		"""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			base = get_computed_base(MODULE)
			self.assertFalse(frappe.db.exists("Sidebar", MODULE))

			name = mark_as_standard(MODULE)

			doc = frappe.get_doc("Sidebar", name)
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
		"""A module that already has a document is shipped verbatim: the computed base is what you get
		when there is nothing to ship, not something that overwrites authored items.
		"""
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
		"""An empty items table is not what the desk renders for the module, since boot fills those
		rows in from the computed base, so shipping the document as it stands would ship a file that
		does not match the navigation it was adopted from.
		"""
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			stub = frappe.new_doc("Sidebar")
			stub.module = MODULE
			stub.header_icon = "hammer"
			stub.insert(ignore_permissions=True)
			self.assertEqual(stub.items, [])

			mark_as_standard(MODULE)

			stub.reload()
			# what it says about itself stands: that is authored, and only the items were missing
			self.assertEqual(stub.header_icon, "hammer")
			self.assertEqual(
				[item_key(row) for row in stub.items],
				[item_key(row) for row in get_computed_base(MODULE).rows],
			)

	def test_renaming_a_standard_sidebar_moves_its_file(self):
		"""The file is named after the record, so a rename has to move it.

		Left where it was, it is a file with no row behind it, and the next `bench migrate` imports it
		back as a second sidebar under the same module.

		"""
		import os

		renamed = "Test Standard Sidebar Renamed"

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			doc = frappe.get_doc("Sidebar", mark_as_standard(MODULE))
			before = doc.exported_file_path()
			self.assertTrue(os.path.exists(before), "sanity: the mark wrote a file")

			doc.title = renamed
			doc.save(ignore_permissions=True)

			self.assertEqual(doc.name, renamed)
			after = frappe.get_doc("Sidebar", renamed).exported_file_path()
			self.assertNotEqual(after, before, "sanity: the path is built from the name")
			self.assertFalse(os.path.exists(os.path.dirname(before)), "the old folder is gone")
			self.assertTrue(os.path.exists(after), f"nothing written to {after}")

	def test_a_site_owned_rename_touches_no_file(self):
		"""Only a standard sidebar has a file to keep in step, and only a developer's site has one to
		write. A rename must not look for a folder that was never there.
		"""
		import os

		with module_resolvable_on_disk(MODULE) as path, developer_mode():
			doc = make_sidebar(MODULE)
			self.assertEqual(doc.standard, 0)

			doc.title = "Test Site Owned Sidebar Renamed"
			doc.save(ignore_permissions=True)

			self.assertEqual(doc.name, "Test Site Owned Sidebar Renamed")
			self.assertFalse(os.path.exists(os.path.join(path, "sidebar")), "nothing was written")

	def test_a_standard_row_whose_file_went_missing_is_written_again(self):
		"""The mark reports what it verified, so being asked again to ship a sidebar that has lost its
		file has to write the file rather than report the row as already done. A standard row without
		one is deleted by the next migrate.
		"""
		import os
		import shutil

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			path = frappe.get_doc("Sidebar", name).exported_file_path()
			shutil.rmtree(os.path.dirname(path))

			mark_as_standard(MODULE)

			self.assertTrue(os.path.exists(path))

	def test_standard_row_survives_orphan_removal(self):
		"""The whole point of writing the file: a standard row without one is an orphan."""
		from frappe.model.sync import remove_orphan_entities

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)

			remove_orphan_entities("Sidebar")
			self.assertTrue(frappe.db.exists("Sidebar", name))

	def test_the_mark_fails_when_the_export_wrote_no_file(self):
		"""Verified, not assumed. A standard row with nothing backing it is an orphan the next migrate
		deletes, so a mark that could not write its file has to leave the module as it found it, with
		no document at all.
		"""
		from unittest.mock import patch

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			with patch("frappe.modules.export_file.export_to_files"):
				with self.assertRaises(frappe.ValidationError):
					mark_as_standard(MODULE)

		self.assertFalse(frappe.db.exists("Sidebar", MODULE))

	def test_marking_needs_developer_mode(self):
		"""Only developer mode writes files, so outside it the mark could only produce a row
		that deletes itself."""
		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			mark_as_standard(MODULE)

		self.assertFalse(frappe.db.exists("Sidebar", MODULE))

	def test_un_marking_needs_developer_mode(self):
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)

			with no_developer_mode(), self.assertRaises(frappe.ValidationError):
				unmark_as_standard(MODULE)

			self.assertTrue(frappe.db.exists("Sidebar", name))

	def test_neither_needs_a_role(self):
		"""The old `Workspace Manager` gate is gone: developer mode is the whole gate, and what is
		left is the doctype's own permissions. A System Manager holds no `Workspace Manager` role and
		is refused nothing here.
		"""
		self.enterContext(
			self.set_user(user_with_roles("test-sidebar-sysmanager@example.com", ["System Manager"]))
		)
		self.assertNotIn("Workspace Manager", frappe.get_roles())

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			self.assertTrue(frappe.db.exists("Sidebar", name))

			unmark_as_standard(MODULE)
			self.assertFalse(frappe.db.exists("Sidebar", name))

	def test_cannot_mark_standard_when_the_module_has_no_folder(self):
		"""No folder means nowhere to write the file, and a standard row without one is an orphan, so
		refuse before creating anything.
		"""
		with developer_mode(), self.assertRaises(frappe.ValidationError):
			mark_as_standard(MODULE)

		self.assertFalse(frappe.db.exists("Sidebar", MODULE))

	def test_un_marking_deletes_the_document_and_its_file(self):
		"""Not a cleared flag: a row that is neither app content nor site intent is a frozen copy of a
		base that has stopped tracking the module. The file has to go too, because left behind, the
		next `bench migrate` re-imports it and marks the row standard again.
		"""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			path = frappe.get_doc("Sidebar", name).exported_file_path()
			self.assertTrue(os.path.exists(path))

			unmark_as_standard(MODULE)

			self.assertFalse(frappe.db.exists("Sidebar", name))
			self.assertFalse(os.path.exists(path))

	def test_un_marking_takes_the_document_it_is_given(self):
		"""A module may own more than one sidebar and this deletes one, so it names the document.

		Told only the module it would have to pick, and the form's button is pressed on a sidebar
		the user is looking at: picking would take a different one away and leave that one on
		screen.

		"""
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			own = mark_as_standard(MODULE)
			other = make_sidebar(MODULE, title="Test Sidebar Second")
			other.standard = 1
			other.app = "frappe"
			other.save(ignore_permissions=True)

			unmark_as_standard(other.name)

			self.assertFalse(frappe.db.exists("Sidebar", other.name))
			self.assertTrue(frappe.db.exists("Sidebar", own), "the other sidebar is untouched")

	def test_un_marking_returns_the_module_to_its_computed_base(self):
		"""In the same request. The document going away is not the module losing its navigation, since
		the base is computed from the module's contents on read.
		"""
		from frappe.desk.doctype.sidebar.sidebar import get_sidebar_bases

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
			path = frappe.get_doc("Sidebar", name).exported_file_path()
			first = self.exported_json(path)

			unmark_as_standard(MODULE)
			self.assertEqual(frappe.get_all("Sidebar", filters={"module": MODULE}), [])

			again = mark_as_standard(MODULE)

			self.assertEqual(again, name)
			self.assertEqual(self.exported_json(path), first)
			self.assertEqual(len(frappe.get_all("Sidebar", filters={"module": MODULE})), 1)

	def test_marking_standard_is_idempotent(self):
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			name = mark_as_standard(MODULE)
			modified = frappe.db.get_value("Sidebar", name, "modified")

			mark_as_standard(MODULE)
			self.assertEqual(frappe.db.get_value("Sidebar", name, "modified"), modified)


APP_ROOT_MODULE = "Test App Rooted Sidebar Module"
APP_ROOT_TITLE = "Test App Rooted Sidebar"


class TestAppRootedSidebar(IntegrationTestCase):
	"""A sidebar that belongs to its app rather than to one of the app's modules.

	`module` may be blank, and a blank one is not a sidebar missing a column: it is a sidebar whose
	home is the app itself. Frappe CRM wanting a shell that is neither `FCRM` nor `Lead Syncing` is
	the case for it, and the app is the only thing left to root it at.

	These tests show that rooting it there costs the export road nothing. The file keeps the ordinary
	shape, a folder named after the record holding a file of the same name, so the import walk finds
	it, orphan cleanup reaps it, and the module-rooted path is built by the same code. The old
	app-level fixtures got that wrong, using a flat folder named after a display field, and every
	piece of app-level machinery downstream existed to compensate.

	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.app_path = frappe.get_app_path("frappe")
		self.clear_sidebars()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.clear_sidebars()
		# `remove_orphan_entities` commits, so a row written before it is already durable and
		# the framework's rollback will not take it back out.
		frappe.db.commit()  # nosemgrep

	def clear_sidebars(self):
		"""Both the rows and anything they left inside the frappe app.

		These tests write real files into the working tree, which is what is under test, so a leaked
		folder is not just untidy: it is a `Sidebar` the next `bench migrate` imports.

		"""
		import contextlib
		import os
		import shutil

		for name in frappe.get_all(
			"Sidebar", filters={"title": ["like", "Test App Rooted Sidebar%"]}, pluck="name"
		):
			frappe.delete_doc("Sidebar", name, force=True, ignore_permissions=True)

		for title in (APP_ROOT_TITLE, f"{APP_ROOT_TITLE} Two"):
			shutil.rmtree(self.app_root_folder(title), ignore_errors=True)

		# frappe ships no app-rooted sidebar, so the `sidebar/` folder itself is ours too --
		# and an empty folder git will not show is exactly the kind of residue that survives a
		# run and confuses the next one.
		with contextlib.suppress(OSError):
			os.rmdir(os.path.join(self.app_path, "sidebar"))

	def app_root_folder(self, title):
		import os

		return os.path.join(self.app_path, "sidebar", frappe.scrub(title))

	def make(self, title=APP_ROOT_TITLE, app="frappe", standard=1):
		"""A sidebar with no module at all, authored the only way one ever is."""
		doc = frappe.new_doc("Sidebar")
		doc.title = title
		doc.app = app
		doc.standard = standard
		doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"})
		with developer_mode():
			return doc.insert(ignore_permissions=True)

	def test_a_sidebar_may_belong_to_no_module(self):
		"""`module` lost `reqd` when the record took its name from the title, and this is what that
		was for: a shell the app owns outright.
		"""
		doc = self.make(standard=0)

		self.assertFalse(doc.module)
		self.assertEqual(frappe.db.get_value("Sidebar", doc.name, "app"), "frappe")

	def test_it_is_exported_to_the_app_root(self):
		import os

		doc = self.make()

		self.assertEqual(
			doc.exported_file_path(),
			os.path.join(self.app_path, "sidebar", "test_app_rooted_sidebar", "test_app_rooted_sidebar.json"),
		)
		self.assertTrue(doc.is_exported())

	def test_the_module_rooted_path_is_unchanged(self):
		"""The export takes a root rather than a module, so the module-rooted path is built by the
		same call and comes out where it always did.
		"""
		import os

		with sidebarless_module(APP_ROOT_MODULE), module_resolvable_on_disk(APP_ROOT_MODULE):
			doc = make_sidebar(APP_ROOT_MODULE, title=f"{APP_ROOT_TITLE} Two")
			scrubbed = frappe.scrub(doc.name)

			self.assertEqual(
				doc.exported_file_path(),
				os.path.join(
					frappe.get_module_path(APP_ROOT_MODULE), "sidebar", scrubbed, f"{scrubbed}.json"
				),
			)

	def test_the_import_walk_finds_it(self):
		"""What makes migrate re-import it: the ordinary walk, pointed at the app instead of a module
		folder. Nothing about the walk itself is new.
		"""
		from frappe.model.sync import APP_ROOTED_DOCTYPES, get_doc_files

		doc = self.make()

		files = get_doc_files(files=[], start_path=self.app_path, doctypes=APP_ROOTED_DOCTYPES)
		self.assertIn(doc.exported_file_path(), files)

	def test_the_app_root_walk_is_allowlisted(self):
		"""App-level export is a narrow, named capability. Reusing the whole importable set at the top
		of an app would make twenty-odd folder names newly meaningful there.
		"""
		import json
		import os
		import shutil

		from frappe.model.sync import APP_ROOTED_DOCTYPES, get_doc_files

		stray = os.path.join(self.app_path, "workspace", "test_app_rooted_stray")
		os.makedirs(stray, exist_ok=True)
		self.addCleanup(shutil.rmtree, os.path.join(self.app_path, "workspace"), ignore_errors=True)
		path = os.path.join(stray, "test_app_rooted_stray.json")
		with open(path, "w") as f:
			json.dump({"doctype": "Workspace", "name": "Test App Rooted Stray"}, f)

		files = get_doc_files(files=[], start_path=self.app_path, doctypes=APP_ROOTED_DOCTYPES)
		self.assertNotIn(path, files)

	def test_migrate_re_imports_it(self):
		from frappe.modules.import_file import import_file_by_path

		doc = self.make()
		path = doc.exported_file_path()
		frappe.delete_doc("Sidebar", doc.name, force=True, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Sidebar", doc.name))

		import_file_by_path(path, force=True, ignore_version=True)

		imported = frappe.get_doc("Sidebar", APP_ROOT_TITLE)
		self.assertEqual(imported.standard, 1)
		self.assertFalse(imported.module)
		self.assertEqual(imported.app, "frappe")
		self.assertEqual([row.link_to for row in imported.items], ["User"])

	def test_deleting_the_file_reaps_the_row(self):
		"""The other half of the round trip, and the reason the sweep stopped selecting a module
		column: a module-less row has to be a candidate, or the app can never stop shipping the
		sidebar.
		"""
		import os
		import shutil

		from frappe.model.sync import remove_orphan_entities

		doc = self.make()
		shutil.rmtree(os.path.dirname(doc.exported_file_path()))

		remove_orphan_entities("Sidebar")

		self.assertFalse(frappe.db.exists("Sidebar", doc.name))

	def test_a_site_owned_module_less_sidebar_is_untouched(self):
		"""Only a standard row is backed by a file, so only a standard row can be an orphan."""
		from frappe.model.sync import remove_orphan_entities

		doc = self.make(standard=0)

		remove_orphan_entities("Sidebar")

		self.assertTrue(frappe.db.exists("Sidebar", doc.name))

	def test_a_standard_sidebar_with_neither_a_module_nor_an_app_is_refused(self):
		"""`standard` means there is a file behind the row, and with no root there is nowhere to put
		one, so the row would delete itself on the next migrate.
		"""
		with self.assertRaises(frappe.ValidationError):
			self.make(app=None)

	def test_a_standard_sidebar_naming_an_uninstalled_app_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(app="not_an_installed_app")

	def test_a_standard_sidebar_cannot_have_its_root_taken_away(self):
		"""Flipping the flag is not the only way to end up standard with no file. Both `module` and
		`app` may be blank now, so clearing whichever one was holding the row up reaches the same
		orphan by another route, and `standard` itself never changes.
		"""
		doc = self.make()
		doc.app = None

		with developer_mode(), self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_a_round_trip_leaves_no_residue(self):
		"""Author, export, migrate, re-import: one row, one folder, and the same file."""
		import os

		from frappe.modules.import_file import import_file_by_path

		doc = self.make()
		path = doc.exported_file_path()
		with open(path) as f:
			exported = f.read()

		frappe.delete_doc("Sidebar", doc.name, force=True, ignore_permissions=True)
		import_file_by_path(path, force=True, ignore_version=True)

		self.assertEqual(
			frappe.get_all("Sidebar", filters={"title": APP_ROOT_TITLE}, pluck="name"), [APP_ROOT_TITLE]
		)
		self.assertEqual(os.listdir(os.path.dirname(path)), [os.path.basename(path)])
		with open(path) as f:
			self.assertEqual(f.read(), exported)


APP_CONTENT_MODULE = "Test App Content Sidebar Module"


class TestSidebarIsAppContent(IntegrationTestCase):
	"""A `Sidebar` belongs to an app, not to the site holding it.

	Only developer mode writes one, which is what makes app updates safe: on a non-developer-mode
	site every sidebar document arrived by import, so overwriting one on an app update costs the site
	nothing. Site intent cannot get into the document at all.

	It goes where it already went instead, to `Custom Sidebar`, at the site-wide layer or the user's
	own, which removes the two ways of authoring the same sidebar with no stated boundary.

	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.module = self.enterContext(sidebarless_module(APP_CONTENT_MODULE))

	def new_sidebar(self):
		doc = frappe.new_doc("Sidebar")
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
		"""Someone the old `Workspace Manager` gate would have turned away.

		Built here rather than picked out of the test records: the shared ones carry whatever roles
		other suites needed, and this test's claim is about holding none.

		"""
		return user_with_roles("test-sidebar-nobody@example.com", [])

	def test_a_desk_user_may_only_read_a_sidebar(self):
		"""An ordinary desk user reads the sidebar the app shipped and writes their own delta instead.
		Their create, write and delete on this doctype were reduced to `read`.
		"""
		perms = {perm.role: perm for perm in frappe.get_meta("Sidebar").permissions}
		desk_user = perms.get("Desk User")

		self.assertIsNotNone(desk_user, "Desk User must still be able to read a sidebar")
		self.assertTrue(desk_user.read)
		self.assertFalse(desk_user.create)
		self.assertFalse(desk_user.write)
		self.assertFalse(desk_user.delete)

	def test_a_customer_site_cannot_write_a_sidebar(self):
		"""Not even as Administrator, and not with permissions ignored: the gate is developer mode,
		not who is asking.
		"""
		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			self.new_sidebar().insert(ignore_permissions=True)

		self.assertFalse(frappe.db.exists("Sidebar", {"module": self.module}))

	def test_a_system_manager_is_no_more_privileged_than_anyone_else(self):
		"""'Regardless of role' includes the roles that can do everything else on a site."""
		self.enterContext(self.set_user("test@example.com"))
		self.assertIn("System Manager", frappe.get_roles())

		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			self.new_sidebar().insert(ignore_permissions=True)

	def test_editing_an_imported_sidebar_is_refused_too(self):
		"""The gate is on writing, not only on creating. A sidebar that arrived by import stays as the
		app wrote it, which is the half of the rule app updates rest on.
		"""
		with system_write():
			imported = self.new_sidebar().insert(ignore_permissions=True)

		imported.title = "Edited by the site"
		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			imported.save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Sidebar", imported.name, "title"), self.module)

	def test_developer_mode_needs_no_role(self):
		"""The same call the customer site refuses, with developer mode on and nothing else different,
		made by a user holding no roles at all, because developer mode is the whole gate and there is
		no role check behind it.
		"""
		self.enterContext(self.set_user(self.roleless_user()))
		self.assertNotIn("Workspace Manager", frappe.get_roles())

		with developer_mode():
			doc = self.new_sidebar().insert(ignore_permissions=True)

		self.assertTrue(frappe.db.exists("Sidebar", doc.name))

	def test_an_import_still_writes_on_a_customer_site(self):
		"""How every sidebar on a customer site gets there. Each of these routes is the system placing
		app content, so gating them would mean an app that ships a sidebar could not be installed or
		updated anywhere.
		"""
		for flag in SYSTEM_WRITE_FLAGS:
			with self.subTest(flag=flag):
				with no_developer_mode(), system_write(flag):
					doc = self.new_sidebar().insert(ignore_permissions=True)

				self.assertTrue(frappe.db.exists("Sidebar", doc.name))
				frappe.delete_doc("Sidebar", doc.name, force=True)

	def test_the_site_keeps_saying_what_it_wants(self):
		"""The point of closing the document: site intent has somewhere better to go, and it still
		goes there on a site that can no longer touch the document at all.
		"""
		from frappe.desk.doctype.custom_sidebar.custom_sidebar import (
			get_customization,
			save_site_sidebar,
		)

		with no_developer_mode():
			save_site_sidebar(self.module, items=[{"key": "whatever", "hidden": 1}])

		site_layer = get_customization(self.module, None)
		self.assertIsNotNone(site_layer)
		self.addCleanup(
			frappe.delete_doc,
			"Custom Sidebar",
			site_layer.name,
			force=True,
			ignore_permissions=True,
		)
		self.assertEqual([(row.key, row.hidden) for row in site_layer.sidebar_items], [("whatever", 1)])

	def test_a_new_workspace_links_itself_through_the_site_layer(self):
		"""The one runtime path that used to write the document. Creating a workspace in a module that
		ships a sidebar has to keep working on a customer site, and the link it earns is site intent,
		so it belongs in the site layer rather than in app content.
		"""
		from frappe.desk.doctype.custom_sidebar.custom_sidebar import (
			get_customization,
		)
		from frappe.desk.doctype.workspace.workspace import add_to_sidebar

		with system_write():
			shipped = self.new_sidebar().insert(ignore_permissions=True)

		# Two, because the module's landing page is the first item of this list, so the one
		# being linked here is deliberately not the one the module opens on.
		self.make_workspace("Test App Content Home")
		workspace = self.make_workspace("Test App Content Workspace")

		with no_developer_mode():
			add_to_sidebar(workspace)

		site_layer = get_customization(self.module, None)
		self.assertIsNotNone(site_layer, "the link has to land somewhere")
		self.addCleanup(
			frappe.delete_doc,
			"Custom Sidebar",
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
		"""The other side of the same branch (D3). A private page's link is derived on read from the
		workspace itself, so writing one would put a row per private page into the document the whole
		site shares, where an admin would find it while curating everyone's navigation.
		"""
		from frappe.desk.doctype.custom_sidebar.custom_sidebar import (
			get_customization,
		)
		from frappe.desk.doctype.workspace.workspace import add_to_sidebar

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
			add_to_sidebar(workspace)

		self.assertIsNone(get_customization(self.module, None), "nothing may be written for it")

	def test_a_page_that_stops_being_private_earns_the_link_it_never_stored(self):
		"""The branch is on what the workspace is, not on when it was created: a page that has just
		been shared has stopped having a derived link, so this is where it gains a stored one.
		Otherwise sharing a page would remove the only way into it.
		"""
		from frappe.desk.doctype.custom_sidebar.custom_sidebar import (
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
			"Custom Sidebar",
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
	"""No path writes a `Sidebar` on a module's behalf.

	Persisting a generated row was what made an app that stops shipping a sidebar leave its module
	un-navigable until the next migrate, and it left rows behind to be orphaned when a module or an
	app went away. The computed base removed the need for it, so the write is gone: a module either
	has a document because someone authored or shipped one, or it has none.

	"""

	def setUp(self):
		frappe.set_user("Administrator")

	def rows_for(self, module):
		return frappe.get_all("Sidebar", filters={"module": module}, pluck="name")

	def test_a_new_module_gets_no_sidebar_document(self):
		"""What installing an app does, one module at a time: the Module Defs land and nothing follows
		them. The module is navigable regardless, because its base is computed.
		"""
		with sidebarless_module("Test Unwritten Sidebar Module") as module:
			self.assertEqual(self.rows_for(module), [])
			self.assertEqual(get_computed_base(module).module, module)

	def test_gaining_content_writes_no_row_either(self):
		"""The other half: a module that gains something navigable is navigable through a base
		computed on the next read, and nothing anywhere turns that into a row.
		"""
		with sidebarless_module("Test Unbuilt Sidebar Module") as module:
			make_report(module, "Test Unbuilt Report")

			self.assertEqual(self.rows_for(module), [])
			self.assertIn("Test Unbuilt Report", [row.link_to for row in get_computed_base(module).rows])


COMPUTED_MODULE = "Test Computed Sidebar Module"


class TestComputedSidebarBase(IntegrationTestCase):
	"""A module nobody shipped a sidebar for is navigable anyway: the system computes its base from
	the module's own contents and site-caches it.

	Under D4 a base has exactly two origins, shipped as an app's JSON or computed here, and only the
	shipped route persists a document. So this route has to work without one: it produces the base
	fresh, and the cache in front of it has to be dropped the moment the module's contents change.

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
		navigation. It is shaped like a stored base so boot cannot tell the two apart.
		"""
		self.make_report("Test Computed Report")
		self.make_page("test-computed-page")

		base = get_computed_base(self.module)

		self.assertEqual(base.module, self.module)
		self.assertEqual(base.title, self.module)
		self.assertEqual(base.app, "frappe")
		self.assertIn(("Report", "Test Computed Report"), self.links(base))
		self.assertIn(("Page", "test-computed-page"), self.links(base))

	def test_nothing_is_persisted(self):
		"""The point of computing: with no row there is nothing to orphan when the module or its app
		goes away, and nothing left behind stale.
		"""
		self.make_report("Test Unpersisted Report")

		get_computed_base(self.module)

		self.assertFalse(frappe.db.exists("Sidebar", {"module": self.module}))

	def test_items_are_identifiable(self):
		"""A delta anchors on a row's identity, so a computed base has to be customizable on the same
		terms as a shipped one: every row identifiable, and no two alike.
		"""
		self.make_report("Test Keyed Report")

		keys = [item_key(row) for row in get_computed_base(self.module).rows]

		self.assertTrue(all(keys))
		self.assertEqual(len(set(keys)), len(keys))

	def test_the_base_is_served_from_the_site_cache(self):
		"""A warm boot reads redis rather than the module's contents, which is what keeps the computed
		route affordable on a site with many sidebar-less modules.
		"""
		self.make_report("Test Cached Report")
		get_computed_base(self.module)

		# a fresh worker: the request-local mirror is empty, so this has to come from redis
		frappe.local.cache.clear()
		with self.assertQueryCount(0):
			base = get_computed_base(self.module)

		self.assertIn(("Report", "Test Cached Report"), self.links(base))

	def test_a_new_report_reaches_the_navigation(self):
		"""The cache is cleared by the module gaining content, so newly created content needs no
		migrate and no restart to show up.
		"""
		get_computed_base(self.module)

		self.make_report("Test Late Report")

		self.assertIn(("Report", "Test Late Report"), self.links(get_computed_base(self.module)))

	def test_a_deleted_page_leaves_the_navigation(self):
		page = self.make_page("test-doomed-page")
		self.assertIn(("Page", page.name), self.links(get_computed_base(self.module)))

		delete_page(page.name)

		self.assertNotIn(("Page", page.name), self.links(get_computed_base(self.module)))

	def test_moving_content_busts_both_modules(self):
		"""A module loses what another gains, so an update touches two caches: the one named on the
		document now and the one it named before.
		"""
		report = self.make_report("Test Migrating Report")
		self.assertIn(("Report", report.name), self.links(get_computed_base(self.module)))

		report.module = "Core"
		report.save(ignore_permissions=True)
		self.addCleanup(clear_computed_base_cache, "Core")

		self.assertNotIn(("Report", report.name), self.links(get_computed_base(self.module)))
		self.assertIn(("Report", report.name), self.links(get_computed_base("Core")))

	def test_every_source_of_content_busts_the_cache(self):
		"""The invalidation set has to equal the read set. If `get_module_info` gains a source whose
		controller does not clear this cache, that source's bases go stale silently.

		It is driven through `clear_cache`, the one method the framework runs on both a save and a
		delete, so it covers the DocType case without creating one. See `make_report` for why no test
		does.

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


class TestAppSidebarLayer(IntegrationTestCase):
	"""The editor's third layer, which is the `Sidebar` document itself.

	The two layers above are `Custom Sidebar` documents laid over a base. This one is the base, so
	arranging it writes the document its app ships and exports the file behind it. A module no app
	shipped a sidebar for starts from the one computed from its contents, which is what the desk
	is already drawing, so the first save turns what is on screen into a fixture.

	Everything here is developer mode only, which is the gate `validate_app_content` already puts
	on writing a `Sidebar` by any other route.

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
		# `remove_orphan_entities` commits, so anything written before it is already durable and
		# the framework's rollback will not undo it. See `TestSidebarStandard.tearDown`.
		frappe.db.commit()  # nosemgrep

	def clear_module_content(self):
		for name in frappe.get_all("Sidebar", filters={"module": MODULE}, pluck="name"):
			frappe.delete_doc("Sidebar", name, force=True, ignore_permissions=True)
		for name in frappe.get_all("Custom Sidebar", filters={"module": MODULE}, pluck="name"):
			frappe.delete_doc("Custom Sidebar", name, force=True, ignore_permissions=True)
		frappe.db.delete("Report", {"module": MODULE})

	def with_content(self):
		"""Two reports, so the module's computed base has an order worth rearranging."""
		make_report(MODULE, "Test App Layer Report A")
		make_report(MODULE, "Test App Layer Report B")
		clear_computed_base_cache(MODULE)

	def rendered(self):
		"""The module's sidebar as the desk draws it, which is where hiding has to show up."""
		from frappe.desk.doctype.sidebar.sidebar import resolve_sidebar

		clear_computed_base_cache(MODULE)
		resolved = resolve_sidebar(MODULE, "Administrator")
		return [item["label"] for item in resolved.items] if resolved else []

	def test_a_module_with_no_document_reads_its_computed_base(self):
		"""The starting point is what the desk already shows.

		Nothing persists a base, so the ordinary state of a module is to have no document, and the
		editor has to open on the sidebar generated from the module's contents rather than on an
		empty list to fill in by hand.

		"""
		with developer_mode():
			self.with_content()
			self.assertFalse(frappe.db.exists("Sidebar", MODULE))

			self.assertEqual(
				[row["key"] for row in get_app_sidebar_layer(MODULE)],
				[item_key(row) for row in get_computed_base(MODULE).rows],
			)

	def test_every_row_reads_as_the_item_rather_than_a_reference_to_one(self):
		"""`added` says a row brings its own item to a layer above a base. This is the base, so
		nothing here adds anything to anything, and the editor has to treat every row as one it may
		hide rather than one it may delete."""
		with developer_mode():
			self.with_content()

			self.assertTrue(all(row["added"] == 0 for row in get_app_sidebar_layer(MODULE)))

	def test_saving_writes_a_standard_document_and_exports_it(self):
		"""One action. The layer is named after the app, and a document that is not standard is not
		the app's: no file backs it and no migrate re-imports it."""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			rows = get_app_sidebar_layer(MODULE)

			save_app_sidebar(MODULE, rows)

			doc = frappe.get_doc("Sidebar", MODULE)
			self.assertEqual(doc.standard, 1)
			self.assertEqual(doc.app, "frappe")
			self.assertTrue(os.path.exists(doc.exported_file_path()))
			self.assertEqual([item_key(row) for row in doc.items], [row["key"] for row in rows])

	def test_saving_stores_the_order_on_screen(self):
		"""The whole arrangement is written, not a delta, so the order the editor was left in is
		the order the document ends up holding."""
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			rows = get_app_sidebar_layer(MODULE)
			reversed_rows = list(reversed(rows))

			save_app_sidebar(MODULE, reversed_rows)

			self.assertEqual(
				[item_key(row) for row in frappe.get_doc("Sidebar", MODULE).items],
				[row["key"] for row in reversed_rows],
			)

	def test_a_hidden_row_is_kept_and_stops_rendering(self):
		"""Hiding is how an entry leaves an app's sidebar, and the row stays so it can come back.

		This is the half that used not to work: a base row's `hidden` was neither read from the
		table nor carried into the merge, so an app could ship one and it would render anyway.

		"""
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			rows = get_app_sidebar_layer(MODULE)
			target = next(row for row in rows if row["link_to"] == "Test App Layer Report A")
			self.assertIn(target["label"], self.rendered())

			target["hidden"] = 1
			save_app_sidebar(MODULE, rows)

			stored = {item_key(row): row.hidden for row in frappe.get_doc("Sidebar", MODULE).items}
			self.assertEqual(stored[target["key"]], 1, "the row was dropped instead of hidden")
			self.assertNotIn(target["label"], self.rendered())

	def test_a_row_left_out_is_deleted_from_the_document_and_the_file(self):
		"""Removing an entry is not the same as hiding it, and this layer is the only one where
		the difference can be had.

		Its arrangement is the base, so a row left out of it is gone: out of the document's table
		and out of the file the save exports, with nothing underneath for it to fall back to. On
		the two layers above, a row left out means "no opinion" and the base shows through, which
		is why hiding is the only way to take something off up there.

		"""
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			rows = get_app_sidebar_layer(MODULE)
			dropped = next(row for row in rows if row["link_to"] == "Test App Layer Report A")

			save_app_sidebar(MODULE, [row for row in rows if row["key"] != dropped["key"]])

			doc = frappe.get_doc("Sidebar", MODULE)
			self.assertNotIn(dropped["key"], [item_key(row) for row in doc.items])

			with open(doc.exported_file_path()) as f:
				exported = json.load(f)
			self.assertNotIn(dropped["link_to"], [item.get("link_to") for item in exported["items"]])

			self.assertNotIn(dropped["label"], self.rendered())

	def test_a_hidden_row_can_be_brought_back(self):
		"""Which is the reason for keeping it. A row that was deleted could only be re-added from
		the pool; one that was hidden is still in the arrangement to un-hide."""
		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			rows = get_app_sidebar_layer(MODULE)
			target = next(row for row in rows if row["link_to"] == "Test App Layer Report A")
			target["hidden"] = 1
			save_app_sidebar(MODULE, rows)

			back = get_app_sidebar_layer(MODULE)
			hidden_again = next(row for row in back if row["key"] == target["key"])
			self.assertEqual(hidden_again["hidden"], 1, "the editor cannot see what it hid")

			hidden_again["hidden"] = 0
			save_app_sidebar(MODULE, back)

			self.assertIn(target["label"], self.rendered())

	def test_a_section_keeps_the_shape_it_was_given(self):
		"""What the editor's pencil decides about a section: whether it draws as a heading over a
		divider or as an indented row with its entries nested under it, and how it folds.

		They are columns like any other, so they survive on the same terms as the rest. This pins
		them because they are the ones the editor offers, and a section whose shape did not
		survive a save would be the one thing the editor cannot work around.

		"""
		shape = {"indent": 1, "collapsible": 0, "show_arrow": 1, "keep_closed": 1}

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			rows = get_app_sidebar_layer(MODULE)
			section = next(row for row in rows if row["type"] == "Section Break")
			section.update(shape)

			save_app_sidebar(MODULE, rows)

			# The key is a hash of the row's type and label, neither of which the shape touches,
			# so the section is still the one that was changed.
			back = next(row for row in get_app_sidebar_layer(MODULE) if row["key"] == section["key"])
			self.assertEqual({field: back[field] for field in shape}, shape)

	def test_the_editor_round_trips_every_column(self):
		"""A save rebuilds the table from what the client sent rather than merging into what was
		stored, so a column the editor does not carry is a column the next save drops.

		This is the only thing that says so. It fails when a column is added to `Sidebar Item`
		and not to `ARRANGED_ITEM_FIELDS`, which is a change nothing else would notice until
		someone arranged a sidebar and lost the value.

		"""
		layout = {"Section Break", "Column Break", "HTML", "Tab Break", "Heading"}
		columns = {
			field.fieldname
			for field in frappe.get_meta("Sidebar Item").fields
			if field.fieldtype not in layout
		}
		# `navigate_to_tab`, `hidden` and `added` are set by `app_item` itself; `key` is cleared
		# by `clear_stored_keys`, for the reason it gives.
		handled = set(ARRANGED_ITEM_FIELDS) | {"navigate_to_tab", "hidden", "added", "key"}

		self.assertEqual(columns - handled, set())

	def test_resetting_removes_the_document_and_its_file(self):
		"""The layer below this one is the computed base, which is worked out on read, so the
		module has a working sidebar again in the same request."""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			save_app_sidebar(MODULE, get_app_sidebar_layer(MODULE))
			path = frappe.get_doc("Sidebar", MODULE).exported_file_path()

			reset_app_sidebar(MODULE)

			self.assertFalse(frappe.db.exists("Sidebar", MODULE))
			self.assertFalse(os.path.exists(path))
			self.assertTrue(self.rendered())

	def test_resetting_reaches_a_sidebar_that_was_renamed(self):
		"""The document the save wrote is the document the reset has to remove.

		A sidebar is named by its title, so a module's shell need not carry the module's name, and
		the read and the save both address it however it is named. A reset that asked the naming
		rule instead would find nothing under the module's name and report success, leaving the
		document on the site and its file in the app.

		"""
		import os

		renamed = "Test App Layer Sidebar Renamed"

		with module_resolvable_on_disk(MODULE), developer_mode():
			self.with_content()
			save_app_sidebar(MODULE, get_app_sidebar_layer(MODULE))
			doc = frappe.get_doc("Sidebar", MODULE)
			doc.title = renamed
			doc.save(ignore_permissions=True)
			path = frappe.get_doc("Sidebar", renamed).exported_file_path()
			self.assertTrue(os.path.exists(path), "sanity: the rename moved the file")

			reset_app_sidebar(MODULE)

			self.assertFalse(frappe.db.exists("Sidebar", renamed))
			self.assertFalse(os.path.exists(path))
			self.assertTrue(self.rendered(), "the module falls back to its computed base")

	def test_the_editor_stays_on_the_sidebar_that_was_on_screen(self):
		"""A module may own more than one sidebar, and the module alone does not say which of them
		the person had open, so all three calls carry the shell.

		Without it they take whichever sidebar comes first by name. They agree with each other, so
		nothing looks broken: the editor reads that one, the save writes it and the reset deletes
		it. They agree on a document nobody was looking at, though, so the rows on screen are not
		the sidebar the desk is drawing, and the reset takes away the wrong one.

		"""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			deals = make_sidebar(MODULE, title="Test App Layer Deals")
			leads = make_sidebar(MODULE, title="Test App Layer Leads")
			for doc, label in ((deals, "Deals Home"), (leads, "Leads Home")):
				doc.items[0].label = label
				doc.save(ignore_permissions=True)

			self.assertEqual(
				get_module_shell(MODULE).name, deals.name, "sanity: the module alone lands elsewhere"
			)

			rows = get_app_sidebar_layer(MODULE, shell=leads.name)
			self.assertEqual([row["label"] for row in rows], ["Leads Home"])

			save_app_sidebar(MODULE, rows, shell=leads.name)
			self.assertTrue(frappe.db.get_value("Sidebar", leads.name, "standard"))
			self.assertFalse(
				frappe.db.get_value("Sidebar", deals.name, "standard"), "the other one is untouched"
			)

			path = frappe.get_doc("Sidebar", leads.name).exported_file_path()
			reset_app_sidebar(MODULE, shell=leads.name)

			self.assertFalse(frappe.db.exists("Sidebar", leads.name))
			self.assertFalse(os.path.exists(path))
			self.assertTrue(frappe.db.exists("Sidebar", deals.name), "the other one survives")

	def test_a_shell_the_module_no_longer_owns_is_refused(self):
		"""An editor left open while that sidebar was renamed is holding a name nothing answers to.

		It is not asking for the fallback. Taking it would arrange, save over or delete whichever
		sidebar comes first by name, which is another shell under the same module and not the one
		anybody had open, and reset makes that unrecoverable: the document goes and its exported
		directory is removed from the app.

		"""
		with module_resolvable_on_disk(MODULE), developer_mode():
			deals = make_sidebar(MODULE, title="Test App Layer Deals")
			leads = make_sidebar(MODULE, title="Test App Layer Leads")
			was = leads.name
			leads.title = "Test App Layer Prospects"
			leads.save(ignore_permissions=True)

			for call in (
				lambda: get_app_sidebar_layer(MODULE, shell=was),
				lambda: save_app_sidebar(MODULE, [], shell=was),
				lambda: reset_app_sidebar(MODULE, shell=was),
			):
				with self.assertRaises(frappe.ValidationError):
					call()

			self.assertTrue(frappe.db.exists("Sidebar", deals.name), "the other one is still there")

	def test_the_module_s_own_name_is_not_a_way_past_the_check(self):
		"""The module's name passes because a computed base has no document to check against. A
		module that does have one, named after itself, is a different case: renaming it leaves the
		editor holding the module's name with nothing behind it, and letting that through lands on
		whichever sidebar comes first by name.
		"""
		with module_resolvable_on_disk(MODULE), developer_mode():
			other = make_sidebar(MODULE, title="Test App Layer Alpha")
			own = make_sidebar(MODULE)
			own.title = "Test App Layer Zebra"
			own.save(ignore_permissions=True)

			with self.assertRaises(frappe.ValidationError):
				reset_app_sidebar(MODULE, shell=MODULE)

			self.assertTrue(frappe.db.exists("Sidebar", other.name), "the other one is still there")

	def test_a_shell_under_another_module_is_ignored(self):
		"""The shell says which of a module's sidebars, and the module still says which module. The
		resolver carries the module into its lookup, so a name belonging elsewhere selects nothing
		and no caller reaches out of the module it named. Refusing such a name, rather than falling
		back, is `check_shell`'s job at the endpoints.
		"""
		with developer_mode():
			own = make_sidebar(MODULE)

			self.assertEqual(get_module_shell(MODULE, "Build").name, own.name)

	def test_none_of_it_works_without_developer_mode(self):
		"""`standard` means a file inside an app, and only a developer's site writes those. The
		editor hides the layer, and each endpoint refuses as well, because the layer being absent
		from a screen is not what stops a call."""
		with developer_mode():
			self.with_content()
			rows = get_app_sidebar_layer(MODULE)

		with no_developer_mode():
			for call in (
				lambda: get_app_sidebar_layer(MODULE),
				lambda: save_app_sidebar(MODULE, rows),
				lambda: reset_app_sidebar(MODULE),
			):
				with self.assertRaises(frappe.ValidationError):
					call()
