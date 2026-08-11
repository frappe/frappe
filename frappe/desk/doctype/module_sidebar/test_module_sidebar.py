# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from collections import Counter
from contextlib import contextmanager

import frappe
from frappe.desk.doctype.module_sidebar.module_sidebar import (
	COMPUTED_BASE_CACHE_KEY,
	MODULE_CONTENT_DOCTYPES,
	SYSTEM_WRITE_FLAGS,
	assign_keys,
	build_all,
	build_module_sidebar,
	clear_computed_base_cache,
	derive_key,
	get_computed_base,
	get_module_sidebar_sources,
	mark_as_standard,
	pick_primary,
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


class TestModuleSidebarKeys(IntegrationTestCase):
	"""The `key` field exists so per-user customization survives an app re-authoring its
	sidebar. These pin the properties that makes that true."""

	def test_key_is_stable_across_regeneration(self):
		"""Same input rows -> same keys, which is what makes re-import safe.

		Standard child rows are hash-named and recreated on every import, so a delta can
		never anchor on `name`. It anchors on `key`, and this is why that works.
		"""

		def keys_for(rows):
			counter = Counter()
			return [derive_key(row, counter) for row in rows]

		rows = [
			{"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"},
			{"type": "Section Break", "label": "Reports"},
			{"type": "Link", "link_type": "Report", "link_to": "Permitted Documents For User"},
			{"type": "Section Break", "label": "Settings"},
		]

		self.assertEqual(keys_for(rows), keys_for(rows))
		# and the two Section Breaks, which collide on everything but their ordinal
		self.assertEqual(len(set(keys_for(rows))), 4)

	def test_key_ignores_label(self):
		"""Renaming an item must not orphan a user's delta -- the whole point of excluding
		`label` from the derivation."""
		counter_a, counter_b = Counter(), Counter()
		before = derive_key(
			{"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"}, counter_a
		)
		after = derive_key(
			{"type": "Link", "link_type": "DocType", "link_to": "User", "label": "People"}, counter_b
		)
		self.assertEqual(before, after)

	def test_ordinals_separate_colliding_items(self):
		"""Excluding the label makes every Section Break collide; the ordinal is what keeps
		them distinct."""
		items = [frappe._dict({"type": "Section Break", "label": f"S{i}"}) for i in range(4)]
		assign_keys(items)
		self.assertEqual(len({item.key for item in items}), 4)

	def test_authored_key_wins(self):
		"""An explicit key is a pin -- the derivation is only the fallback."""
		items = [
			frappe._dict({"type": "Link", "link_type": "DocType", "link_to": "User", "key": "pinned"}),
			frappe._dict({"type": "Link", "link_type": "DocType", "link_to": "Role"}),
		]
		assign_keys(items)
		self.assertEqual(items[0].key, "pinned")
		self.assertTrue(items[1].key)
		self.assertNotEqual(items[1].key, "pinned")


class TestModuleSidebarMerge(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Module Def", MODULE):
			with no_developer_mode():
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": MODULE, "app_name": "frappe"}
				).insert()
		self.workspaces = []

	def tearDown(self):
		frappe.db.delete("Module Sidebar", {"module": MODULE})
		for name in self.workspaces:
			frappe.delete_doc("Workspace", name, force=True, ignore_missing=True)
		with no_developer_mode():
			frappe.delete_doc("Module Def", MODULE, force=True, ignore_missing=True)

	def make_workspace(self, name, items, sequence_id=1):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": name,
				"label": name,
				"module": MODULE,
				"public": 1,
				"content": "[]",
				"sequence_id": sequence_id,
				"sidebar_items": items,
			}
		).insert(ignore_permissions=True)
		self.workspaces.append(doc.name)
		return doc

	def link(self, doctype, label=None):
		return {"type": "Link", "link_type": "DocType", "link_to": doctype, "label": label or doctype}

	def test_largest_sidebar_becomes_primary(self):
		"""`sequence_id` is near-uniform on a real site, so as the primary signal it picks
		arbitrarily -- it hands Accounts to Invoicing(28) over Accounting(49)."""
		self.make_workspace("TSM Small", [self.link("User")], sequence_id=1)
		self.make_workspace("TSM Large", [self.link("Role"), self.link("DocType")], sequence_id=99)

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

	def test_differently_labelled_duplicates_survive(self):
		"""Including `label` in the dedupe key is what preserves a doctype deliberately
		listed under two sections (erpnext's CRM does this with Lead)."""
		self.make_workspace(
			"TSM Deliberate",
			[self.link("User", label="All Users"), self.link("User", label="Active Users")],
		)

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		users = [i for i in plan["items"] if i["link_to"] == "User"]
		self.assertEqual(len(users), 2)

	def test_default_workspace_flag_is_carried(self):
		"""The legacy merge path dropped it, which silently broke `default_workspace_map`
		and the desk's cold-entry resolution."""
		item = self.link("User")
		item["default_workspace"] = 1
		self.make_workspace("TSM Default", [item])

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		self.assertEqual(plan["items"][0]["default_workspace"], 1)

	def test_provenance_is_recorded(self):
		"""`merged_from` plus per-item `source_workspace` are what make the merge reversible,
		so splitting a module later is a command rather than a second migration."""
		self.make_workspace("TSM Primary", [self.link("User"), self.link("Role")])
		self.make_workspace("TSM Second", [self.link("DocType")])

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		self.assertEqual(sorted(json.loads(plan["merged_from"])), ["TSM Primary", "TSM Second"])
		self.assertEqual({i["source_workspace"] for i in plan["items"]}, {"TSM Primary", "TSM Second"})

	def test_merged_row_is_not_standard(self):
		"""`standard` means "backed by a file in an app". A merged row is derived from this
		site's workspaces and has none, so marking it standard gets it deleted as an orphan
		by the very next `bench migrate`."""
		self.make_workspace("TSM Only", [self.link("User")])

		plan = build_module_sidebar(MODULE, get_module_sidebar_sources()[MODULE])
		self.assertEqual(plan["standard"], 0)

	def test_build_is_idempotent(self):
		self.make_workspace("TSM Only", [self.link("User")])

		# in developer mode because the build writes sidebar documents, which is app content;
		# its real caller is a patch, where `frappe.flags.in_patch` clears the same gate
		with developer_mode():
			build_all()
			first = frappe.get_doc("Module Sidebar", MODULE)
			first_items = [(i.key, i.link_to) for i in first.items]

			build_all()
		second = frappe.get_doc("Module Sidebar", MODULE)

		self.assertEqual(first.creation, second.creation)
		self.assertEqual(first_items, [(i.key, i.link_to) for i in second.items])

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

	def test_keys_survive_export_and_reimport(self):
		"""Export to JSON, re-import twice, and assert the deltas would still resolve.

		This is the property `key` exists for. `import_doc` is delete-then-insert and child
		rows are hash-named, so every re-import produces different row `name`s -- a
		customization anchored on `name` would break on every `bench migrate`. Anchored on
		`key` it survives, because the derivation is pure.
		"""
		import os

		from frappe.modules.import_file import import_file_by_path

		self.make_workspace(
			"TSM Export",
			[self.link("User"), self.link("Role"), {"type": "Section Break", "label": "More"}],
		)
		with developer_mode():
			build_all()

		doc = frappe.get_doc("Module Sidebar", MODULE)
		# only a standard row exports; the merge deliberately produces standard=0
		doc.db_set("standard", 1, update_modified=False)
		doc.reload()

		before = {i.key: i.link_to for i in doc.items}
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
			after = {i.key: i.link_to for i in after_doc.items}
			names_after = {i.name for i in after_doc.items}

		self.assertEqual(before, after, "keys must be identical across re-import")
		self.assertNotEqual(names_before, names_after, "sanity: child row names are regenerated")

	def test_legacy_store_is_untouched(self):
		"""Phase 1 is non-destructive: the merge reads `Workspace.sidebar_items` and must
		neither read nor write the legacy `Workspace Sidebar` table."""
		if not frappe.db.exists("DocType", "Workspace Sidebar"):
			self.skipTest("legacy doctype already retired")

		self.make_workspace("TSM Only", [self.link("User")])
		before = frappe.db.count("Workspace Sidebar")
		with developer_mode():
			build_all()
		self.assertEqual(before, frappe.db.count("Workspace Sidebar"))


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
				[(row.key, row.type, row.link_to) for row in doc.items],
				[(row.key, row.type, row.link_to) for row in base.rows],
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
				[row.key for row in stub.items], [row.key for row in get_computed_base(MODULE).rows]
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
				[row.key for row in base.rows], [row.key for row in get_computed_base(MODULE).rows]
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
		# `Page.validate` refuses *any* new page outside developer mode, `standard: No` included,
		# and the test site does not have it on. Nothing is written to disk: the export is gated
		# on `standard == "Yes"`.
		with developer_mode():
			return frappe.get_doc(
				{
					"doctype": "Page",
					"page_name": name,
					"title": name,
					"module": self.module,
					"standard": "No",
				}
			).insert(ignore_permissions=True)

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

	def test_items_carry_keys(self):
		"""A delta anchors on `key`, so a computed base has to be customizable on the same
		terms as a shipped one."""
		self.make_report("Test Keyed Report")

		keys = [row.key for row in get_computed_base(self.module).rows]

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

		frappe.delete_doc("Page", page.name, force=True)

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
