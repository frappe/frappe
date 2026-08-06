# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from collections import Counter
from contextlib import contextmanager

import frappe
from frappe.desk.doctype.module_sidebar.module_sidebar import (
	COMPUTED_BASE_CACHE_KEY,
	MODULE_CONTENT_DOCTYPES,
	assign_keys,
	build_all,
	build_module_sidebar,
	clear_computed_base_cache,
	derive_key,
	get_computed_base,
	get_module_sidebar_sources,
	pick_primary,
	sync_module_sidebars,
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
def sidebarless_module(name, app="frappe"):
	"""A `Module Def` with no `Module Sidebar` -- the state a sparse-rows world produces.

	`Module Def.after_insert` still generates a sidebar for every new module, so getting a
	module without one means taking that back off.
	"""
	with no_developer_mode():
		frappe.get_doc({"doctype": "Module Def", "module_name": name, "app_name": app}).insert()
	frappe.db.delete("Module Sidebar", {"module": name})
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
		# after the Module Def, since its `after_insert` generates a sidebar and every test
		# here wants to build its own
		frappe.db.delete("Module Sidebar", {"module": MODULE})
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

		build_all()
		first = frappe.get_doc("Module Sidebar", MODULE)
		first_items = [(i.key, i.link_to) for i in first.items]

		build_all()
		second = frappe.get_doc("Module Sidebar", MODULE)

		self.assertEqual(first.creation, second.creation)
		self.assertEqual(first_items, [(i.key, i.link_to) for i in second.items])

	def test_every_module_def_gets_a_sidebar(self):
		"""The dock is 1:1 with Module Def, so a module shipping nothing still gets a row."""
		sync_module_sidebars(MODULE)
		self.assertTrue(frappe.db.exists("Module Sidebar", MODULE))
		# built from the module's contents, and site-owned like anything else that is not
		# shipped by an app
		self.assertEqual(frappe.db.get_value("Module Sidebar", MODULE, "standard"), 0)

	def test_a_built_row_cannot_be_made_standard_by_hand(self):
		"""`standard` means backed by a file. Setting it without writing one leaves a row that
		orphan removal deletes on the next migrate, so validate refuses it outright."""
		sync_module_sidebars(MODULE)
		doc = frappe.get_doc("Module Sidebar", MODULE)
		self.assertEqual(doc.standard, 0)
		with self.assertRaises(frappe.ValidationError):
			doc.standard = 1
			doc.save()

	def test_site_owned_row_survives_orphan_removal(self):
		"""Orphan removal only considers standard rows -- a site-owned sidebar has no file by
		definition and must never be mistaken for one whose file went missing."""
		from frappe.model.sync import remove_orphan_entities

		sync_module_sidebars(MODULE)
		remove_orphan_entities("Module Sidebar")
		self.assertTrue(frappe.db.exists("Module Sidebar", MODULE))

	def test_deleting_the_module_removes_its_sidebar(self):
		sync_module_sidebars(MODULE)
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
		build_all()
		self.assertEqual(before, frappe.db.count("Workspace Sidebar"))


class TestModuleSidebarStandard(IntegrationTestCase):
	"""Marking a sidebar standard has to write its file in the same breath.

	`standard` means "backed by a JSON file in an app", and orphan removal deletes a standard
	record whose file is missing -- so a half-done mark is a row that destroys itself on the
	next migrate.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Module Def", MODULE):
			with no_developer_mode():
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": MODULE, "app_name": "frappe"}
				).insert()
		frappe.db.delete("Module Sidebar", {"module": MODULE})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Module Sidebar", {"module": MODULE})
		with no_developer_mode():
			frappe.delete_doc("Module Def", MODULE, force=True, ignore_missing=True)
		# `remove_orphan_entities` commits, so anything these tests wrote before it is already
		# durable and the framework's rollback will not undo it. Commit the cleanup too, or a
		# standard row for a module with no folder outlives the test and breaks every later
		# save of it.
		frappe.db.commit()

	def make_sidebar(self, **kwargs):
		doc = frappe.new_doc("Module Sidebar")
		doc.module = MODULE
		doc.update(kwargs)
		doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "User", "label": "Users"})
		doc.insert(ignore_permissions=True)
		return doc

	def test_marking_standard_writes_the_file(self):
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			doc = self.make_sidebar()
			self.assertEqual(doc.standard, 0)

			doc.mark_as_standard()

			self.assertEqual(doc.standard, 1)
			self.assertEqual(doc.app, "frappe")
			self.assertTrue(os.path.exists(doc.exported_file_path()))

	def test_marking_a_built_sidebar_adopts_it(self):
		"""A sidebar built from the module's contents can be promoted -- "this is good, ship
		it" -- with no separate provenance flag standing in the way."""
		with module_resolvable_on_disk(MODULE), developer_mode():
			doc = self.make_sidebar()
			doc.mark_as_standard()

			self.assertEqual(doc.standard, 1)
			self.assertEqual(doc.app, "frappe")

	def test_standard_row_survives_orphan_removal(self):
		"""The whole point of writing the file: a standard row without one is an orphan."""
		from frappe.model.sync import remove_orphan_entities

		with module_resolvable_on_disk(MODULE), developer_mode():
			doc = self.make_sidebar()
			doc.mark_as_standard()

			remove_orphan_entities("Module Sidebar")
			self.assertTrue(frappe.db.exists("Module Sidebar", doc.name))

	def test_cannot_mark_standard_without_developer_mode(self):
		"""Only developer mode writes files, so outside it the mark could only produce a row
		that deletes itself."""
		doc = self.make_sidebar()
		with no_developer_mode(), self.assertRaises(frappe.ValidationError):
			doc.mark_as_standard()

	def test_cannot_mark_standard_when_the_module_has_no_folder(self):
		doc = self.make_sidebar()
		with developer_mode(), self.assertRaises(frappe.ValidationError):
			doc.mark_as_standard()

		self.assertEqual(frappe.db.get_value("Module Sidebar", doc.name, "standard"), 0)

	def test_unmarking_removes_the_exported_file(self):
		"""Clearing the flag alone would not survive a migrate -- the file would be re-imported
		and mark the row standard again."""
		import os

		with module_resolvable_on_disk(MODULE), developer_mode():
			doc = self.make_sidebar()
			doc.mark_as_standard()
			path = doc.exported_file_path()
			self.assertTrue(os.path.exists(path))

			doc.unmark_as_standard()

			self.assertEqual(doc.standard, 0)
			self.assertFalse(os.path.exists(path))

	def test_marking_standard_is_idempotent(self):
		with module_resolvable_on_disk(MODULE), developer_mode():
			doc = self.make_sidebar()
			doc.mark_as_standard()
			modified = doc.modified

			doc.mark_as_standard()
			self.assertEqual(doc.modified, modified)


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
