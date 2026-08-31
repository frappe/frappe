# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from contextlib import contextmanager

import frappe
from frappe.desk.doctype.sidebar.sidebar import (
	ARRANGED_ITEM_FIELDS,
	COMPUTED_BASE_CACHE_KEY,
	MODULE_CONTENT_DOCTYPES,
	SYSTEM_WRITE_FLAGS,
	clear_computed_base_cache,
	filter_sidebar_items,
	get_app_sidebar_layer,
	get_computed_base,
	get_sidebar,
	item_key,
	mark_as_standard,
	reset_app_sidebar,
	save_app_sidebar,
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

		with self.assertRaises(frappe.DuplicateEntryError):
			make_sidebar(self.MODULE, title=self.LEADS)

	def test_the_title_index_catches_a_row_whose_name_has_drifted(self):
		"""What `unique` on `title` buys over the primary key, which already forbids two records of
		one name.

		A row written straight to the table, such as a legacy row or a raw update that skips
		`_sync_autoname_field`, can carry a title its name does not match. The index refuses to let a
		second sidebar claim that title, and nothing else would.

		"""
		drifted = make_sidebar(self.MODULE)
		frappe.db.set_value("Sidebar", drifted.name, "title", self.LEADS, update_modified=False)

		with self.assertRaises(frappe.UniqueValidationError):
			make_sidebar(self.MODULE, title=self.LEADS)

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
