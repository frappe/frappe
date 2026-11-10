# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from json import dumps, loads
from unittest.mock import patch

import frappe
from frappe.desk.page.workspace_restore.workspace_restore import (
	decode_content,
	get_restorable_workspaces,
	replay_versions,
	restore_workspace_edits,
)
from frappe.modules.import_file import import_doc
from frappe.tests import IntegrationTestCase

BASE_CONTENT = [{"id": "s1", "type": "shortcut", "data": {"shortcut_name": "My ToDos", "col": 4}}]
MESSAGE_BLOCK = {
	"id": "m1",
	"type": "paragraph",
	"data": {"text": '<span class="h4">This is a custom message</span>', "col": 12},
}
AUDIT_BLOCK = {"id": "s2", "type": "shortcut", "data": {"shortcut_name": "Audit", "col": 4}}
AUDIT_SHORTCUT = {"type": "DocType", "link_to": "ToDo", "label": "Audit"}


def version_row(**diff) -> frappe._dict:
	"""A Version row the way `get_versions` hands them to the replay."""
	return frappe._dict(
		creation="2025-06-01 00:00:00",
		owner="Administrator",
		diff={"changed": [], "added": [], "removed": [], "row_changed": [], **diff},
	)


def child_row(parentfield: str, **fields) -> dict:
	"""A child row dict as `Version.get_diff` records it, bookkeeping columns included."""
	return {
		"name": frappe.generate_hash(length=10),
		"owner": "Administrator",
		"creation": "2025-06-01 00:00:00",
		"modified": "2025-06-01 00:00:00",
		"modified_by": "Administrator",
		"docstatus": 0,
		"idx": fields.pop("idx", 1),
		"parent": "Replay Base",
		"parentfield": parentfield,
		"parenttype": "Workspace",
		"doctype": frappe.get_meta("Workspace").get_field(parentfield).options,
		**fields,
	}


def make_base_doc():
	doc = frappe.new_doc("Workspace")
	doc.label = doc.title = "Replay Base"
	doc.module = "Desk"
	doc.public = 1
	doc.standard = 1
	doc.icon = "folder"
	doc.content = dumps(BASE_CONTENT)
	doc.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "My ToDos"})
	doc.append("roles", {"role": "Desk User"})
	return doc


class TestReplay(IntegrationTestCase):
	"""The fold from Version rows to a delta payload, on in-memory docs."""

	def test_layout_comes_from_the_newest_content_change(self):
		first = version_row(changed=[["content", dumps(BASE_CONTENT), dumps([*BASE_CONTENT, MESSAGE_BLOCK])]])
		second = version_row(
			changed=[["content", dumps([*BASE_CONTENT, MESSAGE_BLOCK]), dumps([MESSAGE_BLOCK])]]
		)
		replay = replay_versions([first, second], make_base_doc())
		self.assertEqual(replay.content, [MESSAGE_BLOCK])

	def test_added_shortcut_becomes_a_widget_without_bookkeeping_keys(self):
		row = version_row(
			changed=[["content", dumps(BASE_CONTENT), dumps([*BASE_CONTENT, AUDIT_BLOCK])]],
			added=[["shortcuts", child_row("shortcuts", **AUDIT_SHORTCUT)]],
		)
		replay = replay_versions([row], make_base_doc())
		self.assertEqual(replay.widgets, {"shortcut": [AUDIT_SHORTCUT]})

	def test_widget_added_then_removed_is_dropped(self):
		added = version_row(
			changed=[["content", dumps(BASE_CONTENT), dumps([*BASE_CONTENT, AUDIT_BLOCK])]],
			added=[["shortcuts", child_row("shortcuts", **AUDIT_SHORTCUT)]],
		)
		removed = version_row(
			changed=[["content", dumps([*BASE_CONTENT, AUDIT_BLOCK]), dumps(BASE_CONTENT)]],
			removed=[["shortcuts", child_row("shortcuts", **AUDIT_SHORTCUT)]],
		)
		replay = replay_versions([added, removed], make_base_doc())
		self.assertEqual(replay.widgets, {})

	def test_widget_replaced_in_one_save_keeps_the_replacement(self):
		first = child_row("shortcuts", type="DocType", link_to="ToDo", label="Audit")
		second = child_row("shortcuts", type="DocType", link_to="Note", label="Audit")
		replay = replay_versions(
			[
				version_row(
					changed=[["content", None, dumps([*BASE_CONTENT, AUDIT_BLOCK])]],
					added=[["shortcuts", first]],
				),
				version_row(added=[["shortcuts", second]], removed=[["shortcuts", first]]),
			],
			make_base_doc(),
		)
		self.assertEqual([s["link_to"] for s in replay.widgets["shortcut"]], ["Note"])

	def test_hidden_is_carried_and_a_moved_workspace_is_reported_once(self):
		replay = replay_versions(
			[
				version_row(changed=[["content", None, dumps(BASE_CONTENT)], ["is_hidden", 0, "1"]]),
				version_row(changed=[["sequence_id", "2.00", "5.00"]]),
				version_row(changed=[["sequence_id", "5.00", "7.00"]]),
			],
			make_base_doc(),
		)
		self.assertEqual(replay.properties["visibility"], "Hidden")
		self.assertEqual(len(replay.warnings), 1)

	def test_flat_link_rows_regroup_into_a_card(self):
		block = {"id": "c1", "type": "card", "data": {"card_name": "My Card", "col": 4}}
		row = version_row(
			changed=[["content", dumps(BASE_CONTENT), dumps([*BASE_CONTENT, block])]],
			added=[
				["links", child_row("links", idx=5, type="Card Break", label="My Card", link_count=0)],
				[
					"links",
					child_row("links", idx=6, type="Link", label="Note", link_type="DocType", link_to="Note"),
				],
				[
					"links",
					child_row("links", idx=7, type="Link", label="ToDo", link_type="DocType", link_to="ToDo"),
				],
			],
		)
		replay = replay_versions([row], make_base_doc())
		(card,) = replay.widgets["card"]
		self.assertEqual(card["label"], "My Card")
		self.assertEqual(card["link_count"], 2)
		self.assertEqual([link["link_to"] for link in loads(card["links"])], ["Note", "ToDo"])

	def test_link_added_to_a_shipped_card_is_reported(self):
		row = version_row(
			changed=[["content", dumps(BASE_CONTENT), dumps(BASE_CONTENT)]],
			added=[
				["links", child_row("links", type="Link", label="Note", link_type="DocType", link_to="Note")]
			],
		)
		replay = replay_versions([row], make_base_doc())
		self.assertEqual(replay.widgets, {})
		self.assertTrue(any("Note" in warning for warning in replay.warnings))

	def test_a_typed_label_is_escaped_in_warnings(self):
		label = '<img src=x onerror="alert(1)">'
		row = version_row(
			changed=[["content", dumps(BASE_CONTENT), dumps(BASE_CONTENT)]],
			added=[
				["links", child_row("links", type="Link", label=label, link_type="DocType", link_to="Note")]
			],
		)
		(warning,) = replay_versions([row], make_base_doc()).warnings
		self.assertNotIn("<img", warning)
		self.assertIn("&lt;img", warning)

	def test_shipped_widget_edited_in_place_is_reported_not_carried(self):
		edited = {"type": "DocType", "link_to": "Note", "label": "My ToDos"}
		row = version_row(
			changed=[["content", dumps(BASE_CONTENT), dumps(BASE_CONTENT)]],
			added=[["shortcuts", child_row("shortcuts", **edited)]],
		)
		replay = replay_versions([row], make_base_doc())
		self.assertEqual(replay.widgets, {})
		self.assertTrue(any("My ToDos" in warning for warning in replay.warnings))

	def test_roles_end_as_a_net_diff_against_the_base(self):
		row = version_row(
			changed=[["content", dumps(BASE_CONTENT), dumps(BASE_CONTENT)]],
			added=[
				["roles", child_row("roles", role="Desk User")],
				["roles", child_row("roles", role="Workspace Manager")],
			],
			removed=[["roles", child_row("roles", role="System Manager")]],
		)
		replay = replay_versions([row], make_base_doc())
		# Desk User is already in the base: a v15 delete-and-re-add, not a site decision
		self.assertEqual(replay.added_roles, ["Workspace Manager"])
		# System Manager was never in the base, so there is nothing to remove
		self.assertEqual(replay.removed_roles, [])

	def test_row_changed_and_unknown_fields_are_reported(self):
		row = version_row(
			changed=[["content", dumps(BASE_CONTENT), dumps(BASE_CONTENT)], ["parent_page", "", "Tools"]],
			row_changed=[["shortcuts", 0, "abc", [["label", "My ToDos", "Mine"]]]],
		)
		replay = replay_versions([row], make_base_doc())
		self.assertEqual(len(replay.warnings), 2)

	def test_icon_and_translated_colour_are_carried(self):
		row = version_row(
			changed=[
				["content", dumps(BASE_CONTENT), dumps(BASE_CONTENT)],
				["icon", "folder", "cable"],
				["indicator_color", "", frappe._("blue", context="Custom Workspace")],
			]
		)
		replay = replay_versions([row], make_base_doc())
		self.assertEqual(replay.properties, {"icon": "cable", "indicator_color": "blue"})

	def test_content_with_br_decodes(self):
		pretty = dumps([MESSAGE_BLOCK], indent=1).replace("\n", "<br>")
		self.assertEqual(decode_content(pretty), [MESSAGE_BLOCK])
		self.assertIsNone(decode_content("not json"))


class TestWorkspaceRestore(IntegrationTestCase):
	"""The upgrade story end to end: edit in place, lose it to the import, bring it back."""

	WORKSPACE = "Restore Test Workspace"
	MANAGER = "test-workspace-restore-manager@example.com"
	DESK_USER = "test-workspace-restore-user@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		# get_workspaces is request-cached and no request ends inside a test run
		self.clear_request_cache()
		self.addCleanup(self.clear_request_cache)
		self.make_user(self.MANAGER, ["Desk User", "Workspace Manager"])
		self.make_user(self.DESK_USER, ["Desk User"])

		doc = frappe.new_doc("Workspace")
		doc.label = doc.title = self.WORKSPACE
		doc.module = "Desk"
		doc.public = 1
		doc.standard = 1
		doc.content = dumps(BASE_CONTENT)
		doc.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "My ToDos"})
		doc.insert(ignore_if_duplicate=True)
		# what the app's JSON holds, for the re-import that plays the upgrade
		self.shipped = loads(frappe.as_json(frappe.get_doc("Workspace", self.WORKSPACE).as_dict()))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.delete_doc_if_exists("Custom Workspace", self.WORKSPACE)
		frappe.db.delete("Version", {"ref_doctype": "Workspace", "docname": self.WORKSPACE})
		frappe.db.delete("Deleted Document", {"deleted_doctype": "Workspace", "deleted_name": self.WORKSPACE})
		frappe.db.delete("Workspace", {"name": self.WORKSPACE})
		# the parent alone would leave its rows behind for the next test to render
		for table in frappe.get_meta("Workspace").get_table_fields():
			frappe.db.delete(table.options, {"parent": self.WORKSPACE, "parenttype": "Workspace"})

	def clear_request_cache(self):
		if getattr(frappe.local, "request_cache", None):
			frappe.local.request_cache.clear()

	def make_user(self, email, roles):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": email.split("@")[0],
					"send_welcome_email": 0,
					"roles": [{"role": role} for role in roles],
				}
			).insert(ignore_permissions=True)

	def edit_in_place(self, blocks, shortcut=None):
		"""What a v16 editor save did: write the base and leave a Version row behind.

		Tests lift the standard-content guard and default to `ignore_version=True`, so the
		Version has to be asked for.
		"""
		doc = frappe.get_doc("Workspace", self.WORKSPACE)
		doc.content = dumps(blocks)
		if shortcut:
			doc.append("shortcuts", shortcut)
		doc.save(ignore_permissions=True, ignore_version=False)

	def upgrade(self, shipped=None):
		"""The migrate re-import: the shipped JSON replaces the row, Version rows stay."""
		import_doc(dict(shipped or self.shipped), ignore_version=True)

	def shipped_without_shortcuts(self):
		"""A newer app version that dropped the shipped shortcut and its block."""
		return {**self.shipped, "content": dumps([]), "shortcuts": []}

	def listed(self):
		return next((row for row in get_restorable_workspaces() if row["workspace"] == self.WORKSPACE), None)

	def test_edit_is_listed_before_and_after_the_upgrade(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		frappe.set_user(self.MANAGER)
		self.assertEqual(self.listed()["state"], "Not yet overwritten")

		frappe.set_user("Administrator")
		self.upgrade()
		self.assertNotIn("custom message", frappe.db.get_value("Workspace", self.WORKSPACE, "content"))
		frappe.set_user(self.MANAGER)
		row = self.listed()
		self.assertEqual(row["state"], "Overwritten")
		self.assertEqual(row["summary"]["blocks"], 2)

	def test_restore_brings_the_layout_and_added_widget_back(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK, AUDIT_BLOCK], shortcut=AUDIT_SHORTCUT)
		self.upgrade()

		frappe.set_user(self.MANAGER)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			payload = restore_workspace_edits(self.WORKSPACE)
		self.assertEqual(payload["warnings"], [])

		from frappe.desk.desktop import get_desktop_page, get_workspaces

		page = next(p for p in get_workspaces()["pages"] if p["name"] == self.WORKSPACE)
		self.assertEqual(loads(page["content"]), [*BASE_CONTENT, MESSAGE_BLOCK, AUDIT_BLOCK])
		rendered = get_desktop_page({"name": self.WORKSPACE, "title": self.WORKSPACE, "public": 1})
		self.assertIn("Audit", [s.label for s in rendered["shortcuts"]["items"]])
		# the base stays the app's
		self.assertEqual(loads(frappe.db.get_value("Workspace", self.WORKSPACE, "content")), BASE_CONTENT)
		self.assertEqual(self.listed()["state"], "Restored")

	def copies_kept(self):
		return frappe.db.count(
			"Deleted Document", {"deleted_doctype": "Workspace", "deleted_name": self.WORKSPACE}
		)

	def test_upgrade_keeps_a_copy_only_of_an_edited_workspace(self):
		self.upgrade()
		self.assertEqual(self.copies_kept(), 0)
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		self.upgrade()
		self.assertEqual(self.copies_kept(), 1)

	def test_a_shipped_shortcut_the_new_version_dropped_comes_back(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		self.upgrade(self.shipped_without_shortcuts())
		self.assertEqual(frappe.db.count("Workspace Shortcut", {"parent": self.WORKSPACE}), 0)

		frappe.set_user(self.MANAGER)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			payload = restore_workspace_edits(self.WORKSPACE)
		self.assertEqual(payload["warnings"], [])

		from frappe.desk.desktop import get_desktop_page

		rendered = get_desktop_page({"name": self.WORKSPACE, "title": self.WORKSPACE, "public": 1})
		self.assertIn("My ToDos", [s.label for s in rendered["shortcuts"]["items"]])

	def test_a_later_upgrade_keeps_the_copy_that_holds_the_edit(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		self.upgrade(self.shipped_without_shortcuts())
		self.upgrade(self.shipped_without_shortcuts())
		self.assertEqual(self.copies_kept(), 1)

		# a site upgraded before this fix kept a copy of the app's own row as well
		from frappe.model.delete_doc import add_to_deleted_document

		add_to_deleted_document(frappe.get_doc("Workspace", self.WORKSPACE))
		frappe.set_user(self.MANAGER)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			payload = restore_workspace_edits(self.WORKSPACE)
		self.assertEqual(payload["warnings"], [])

		from frappe.desk.desktop import get_desktop_page

		rendered = get_desktop_page({"name": self.WORKSPACE, "title": self.WORKSPACE, "public": 1})
		self.assertIn("My ToDos", [s.label for s in rendered["shortcuts"]["items"]])

	def test_a_dropped_widget_with_no_copy_is_reported(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		self.upgrade(self.shipped_without_shortcuts())
		frappe.db.delete("Deleted Document", {"deleted_doctype": "Workspace", "deleted_name": self.WORKSPACE})
		frappe.set_user(self.MANAGER)
		row = self.listed()
		self.assertTrue(any("My ToDos" in warning for warning in row["warnings"]))

	def test_restore_is_idempotent(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		self.upgrade()
		frappe.set_user(self.MANAGER)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			restore_workspace_edits(self.WORKSPACE)
			first = frappe.get_doc("Custom Workspace", self.WORKSPACE).as_dict()
			restore_workspace_edits(self.WORKSPACE)
			second = frappe.get_doc("Custom Workspace", self.WORKSPACE).as_dict()
		self.assertEqual(first["content"], second["content"])
		self.assertEqual(frappe.db.count("Custom Workspace", {"workspace": self.WORKSPACE}), 1)

	def test_a_later_site_customization_is_flagged(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		self.upgrade()
		frappe.get_doc(
			{"doctype": "Custom Workspace", "workspace": self.WORKSPACE, "content": dumps(BASE_CONTENT)}
		).insert()
		frappe.set_user(self.MANAGER)
		self.assertEqual(self.listed()["state"], "Customized since")

	def test_restore_again_replaces_later_settings(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		self.upgrade()
		frappe.set_user(self.MANAGER)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			restore_workspace_edits(self.WORKSPACE)
			customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
			customization.icon = "cable"
			customization.append("added_roles", {"role": "System Manager"})
			customization.save()
			self.assertEqual(self.listed()["state"], "Customized since")

			restore_workspace_edits(self.WORKSPACE)
		customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
		self.assertFalse(customization.icon)
		self.assertEqual(customization.added_roles, [])
		self.assertEqual(self.listed()["state"], "Restored")

	def test_requires_workspace_manager(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		frappe.set_user(self.DESK_USER)
		self.assertRaises(frappe.PermissionError, get_restorable_workspaces)
		self.assertRaises(frappe.PermissionError, restore_workspace_edits, self.WORKSPACE)

	def test_developer_mode_lists_nothing_and_refuses_the_write(self):
		self.edit_in_place([*BASE_CONTENT, MESSAGE_BLOCK])
		frappe.set_user(self.MANAGER)
		with patch.dict(frappe.conf, {"developer_mode": 1}):
			# an author's edits live in the app's JSON, not in a customization
			self.assertIsNone(self.listed())
			self.assertRaises(frappe.ValidationError, restore_workspace_edits, self.WORKSPACE)

	def test_an_edit_without_a_layout_change_is_not_listed(self):
		doc = frappe.get_doc("Workspace", self.WORKSPACE)
		doc.icon = "cable"
		doc.save(ignore_permissions=True, ignore_version=False)
		self.assertTrue(frappe.db.exists("Version", {"ref_doctype": "Workspace", "docname": self.WORKSPACE}))
		frappe.set_user(self.MANAGER)
		self.assertIsNone(self.listed())
