# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from collections import Counter
from contextlib import contextmanager

import frappe
from frappe.desk.doctype.module_sidebar.module_sidebar import (
	assign_keys,
	build_all,
	build_module_sidebar,
	derive_key,
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
		frappe.db.delete("Module Sidebar", {"module": MODULE})
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
		self.assertEqual(frappe.db.get_value("Module Sidebar", MODULE, "generated"), 1)

	def test_generated_row_is_never_standard(self):
		"""A generated row has no file by design; `standard` would make orphan removal
		delete it on the next migrate."""
		sync_module_sidebars(MODULE)
		doc = frappe.get_doc("Module Sidebar", MODULE)
		self.assertEqual(doc.standard, 0)
		with self.assertRaises(frappe.ValidationError):
			doc.standard = 1
			doc.save()

	def test_generated_row_survives_orphan_removal(self):
		"""Regression guard for the path collision: orphan removal deletes standard rows
		whose backing file is gone, and a generated row has never had one."""
		from frappe.model.sync import remove_orphan_entities

		sync_module_sidebars(MODULE)
		remove_orphan_entities("Module Sidebar")
		self.assertTrue(frappe.db.exists("Module Sidebar", MODULE))

	def test_deleting_the_module_removes_its_sidebar(self):
		sync_module_sidebars(MODULE)
		frappe.delete_doc("Module Def", MODULE, force=True)
		self.assertFalse(frappe.db.exists("Module Sidebar", MODULE))

	def test_legacy_store_is_untouched(self):
		"""Phase 1 is non-destructive: the merge reads `Workspace.sidebar_items` and must
		neither read nor write the legacy `Workspace Sidebar` table."""
		if not frappe.db.exists("DocType", "Workspace Sidebar"):
			self.skipTest("legacy doctype already retired")

		self.make_workspace("TSM Only", [self.link("User")])
		before = frappe.db.count("Workspace Sidebar")
		build_all()
		self.assertEqual(before, frappe.db.count("Workspace Sidebar"))
