# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.kanban_board import kanban_board as kb
from frappe.desk.doctype.kanban_board.kanban_board import (
	get_kanban_board_data,
	get_kanban_column_order_and_index,
	get_kanban_column_page,
	update_order,
	update_order_for_single_card,
)
from frappe.tests import IntegrationTestCase
from frappe.utils import cint


def _decompress_kanban_cards(cards):
	if isinstance(cards, dict) and cards.get("keys"):
		return [dict(zip(cards["keys"], values, strict=True)) for values in cards["values"]]
	return cards or []


class TestKanbanBoard(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.board_name = "_Test Kanban Order Board"
		if frappe.db.exists("Kanban Board", cls.board_name):
			frappe.delete_doc("Kanban Board", cls.board_name, force=1)

		cls.todos = []
		for i, status in enumerate(["Open", "Open", "Open", "Closed"]):
			doc = frappe.get_doc(
				{
					"doctype": "ToDo",
					"description": f"Kanban order test {i}",
					"status": status,
				}
			).insert(ignore_permissions=True)
			cls.todos.append(doc.name)

		board = frappe.get_doc(
			{
				"doctype": "Kanban Board",
				"kanban_board_name": cls.board_name,
				"reference_doctype": "ToDo",
				"field_name": "status",
				"private": 1,
				"filters": frappe.as_json([["ToDo", "name", "in", cls.todos]]),
				"columns": [
					{
						"column_name": "Open",
						"order": frappe.as_json(cls.todos[:3]),
					},
					{
						"column_name": "Closed",
						"order": frappe.as_json(cls.todos[3:]),
					},
				],
			}
		).insert(ignore_permissions=True)
		cls.board_name = board.name

	@classmethod
	def tearDownClass(cls):
		if frappe.db.exists("Kanban Board", cls.board_name):
			frappe.delete_doc("Kanban Board", cls.board_name, force=1)
		for name in cls.todos:
			if frappe.db.exists("ToDo", name):
				frappe.delete_doc("ToDo", name, force=1)
		super().tearDownClass()

	def setUp(self):
		board = frappe.get_doc("Kanban Board", self.board_name)
		board.filters = frappe.as_json([["ToDo", "name", "in", self.todos]])
		board.columns[0].order = frappe.as_json(self.todos[:3])
		board.columns[1].order = frappe.as_json(self.todos[3:])
		board.save(ignore_permissions=True)
		for i, status in enumerate(["Open", "Open", "Open", "Closed"]):
			frappe.db.set_value("ToDo", self.todos[i], "status", status)

	def test_update_order_for_single_card_with_order_arrays_same_column(self):
		open_order, _ = get_kanban_column_order_and_index(
			frappe.get_doc("Kanban Board", self.board_name), "Open"
		)
		moved = open_order.pop(0)
		open_order.insert(1, moved)

		update_order_for_single_card(
			board_name=self.board_name,
			docname=moved,
			from_colname="Open",
			to_colname="Open",
			from_order=open_order,
			to_order=open_order,
		)

		saved_order, _ = get_kanban_column_order_and_index(
			frappe.get_doc("Kanban Board", self.board_name), "Open"
		)
		self.assertEqual(saved_order[1], moved)
		self.assertEqual(len(saved_order), 3)

	def test_update_order_for_single_card_with_order_arrays_cross_column(self):
		board = frappe.get_doc("Kanban Board", self.board_name)
		open_order, _ = get_kanban_column_order_and_index(board, "Open")
		closed_order, _ = get_kanban_column_order_and_index(board, "Closed")

		moved = open_order.pop(1)
		closed_order.insert(0, moved)

		update_order_for_single_card(
			board_name=self.board_name,
			docname=moved,
			from_colname="Open",
			to_colname="Closed",
			from_order=open_order,
			to_order=closed_order,
		)

		board.reload()
		open_order, _ = get_kanban_column_order_and_index(board, "Open")
		closed_order, _ = get_kanban_column_order_and_index(board, "Closed")

		self.assertNotIn(moved, open_order)
		self.assertEqual(closed_order[0], moved)
		self.assertEqual(frappe.db.get_value("ToDo", moved, "status"), "Closed")

	def test_update_order_for_single_card_legacy_indices(self):
		board = frappe.get_doc("Kanban Board", self.board_name)
		open_order, _ = get_kanban_column_order_and_index(board, "Open")
		if len(open_order) < 2:
			self.skipTest("Need at least two Open cards")

		update_order_for_single_card(
			board_name=self.board_name,
			docname=open_order[0],
			from_colname="Open",
			to_colname="Open",
			old_index=0,
			new_index=1,
		)

		saved_order, _ = get_kanban_column_order_and_index(
			frappe.get_doc("Kanban Board", self.board_name), "Open"
		)
		self.assertEqual(saved_order[1], open_order[0])

	def test_update_order_bulk(self):
		board = frappe.get_doc("Kanban Board", self.board_name)
		open_order, _ = get_kanban_column_order_and_index(board, "Open")
		reversed_open = list(reversed(open_order))

		update_order(
			self.board_name,
			frappe.as_json({"Open": reversed_open, "Closed": []}),
		)

		saved_order, _ = get_kanban_column_order_and_index(
			frappe.get_doc("Kanban Board", self.board_name), "Open"
		)
		self.assertEqual(saved_order, reversed_open)

	def test_update_order_skips_missing_docs(self):
		"""On-load sync must not throw when saved order still lists deleted cards."""
		missing = "ToDo-does-not-exist"
		open_with_stale = [self.todos[0], missing, self.todos[1], self.todos[2]]

		board, updated = update_order(
			self.board_name,
			frappe.as_json({"Open": open_with_stale, "Closed": self.todos[3:]}),
		)

		saved_order, _ = get_kanban_column_order_and_index(board, "Open")
		self.assertEqual(saved_order, [self.todos[0], self.todos[1], self.todos[2]])
		self.assertNotIn(missing, saved_order)
		self.assertEqual(updated, [])

	def test_get_kanban_board_data(self):
		frappe.local.form_dict = frappe._dict(
			{
				"board_name": self.board_name,
				"doctype": "ToDo",
				"fields": '["name", "status", "description"]',
				"filters": "[]",
				"kanban_page_length": 50,
			}
		)

		result = get_kanban_board_data()
		open_data = result["columns"]["Open"]
		closed_data = result["columns"]["Closed"]

		self.assertEqual(open_data["total"], 3)
		self.assertEqual(closed_data["total"], 1)
		self.assertEqual(len(_decompress_kanban_cards(open_data["cards"])), 3)
		self.assertEqual(len(_decompress_kanban_cards(closed_data["cards"])), 1)

	def test_on_change_clears_only_reference_doctype_user_settings(self):
		from frappe.model.utils import user_settings

		user = frappe.session.user
		user_settings.update_user_settings("ToDo", {"sentinel": "ref"})
		user_settings.update_user_settings("User", {"sentinel": "other"})

		self.assertIsNotNone(frappe.cache.hget("_user_settings", f"ToDo::{user}"))
		self.assertIsNotNone(frappe.cache.hget("_user_settings", f"User::{user}"))

		frappe.get_doc("Kanban Board", self.board_name).save(ignore_permissions=True)

		self.assertIsNone(frappe.cache.hget("_user_settings", f"ToDo::{user}"))
		self.assertIsNotNone(frappe.cache.hget("_user_settings", f"User::{user}"))

		frappe.cache.hdel("_user_settings", f"User::{user}")

	def test_get_kanban_column_page(self):
		frappe.local.form_dict = frappe._dict(
			{
				"board_name": self.board_name,
				"column_name": "Open",
				"doctype": "ToDo",
				"fields": '["name", "status", "description"]',
				"filters": "[]",
				"kanban_start": 0,
				"kanban_page_length": 2,
			}
		)

		first_page = get_kanban_column_page()
		self.assertEqual(first_page["total"], 3)
		self.assertEqual(len(_decompress_kanban_cards(first_page["cards"])), 2)

		frappe.local.form_dict["kanban_start"] = 2
		second_page = get_kanban_column_page()
		self.assertEqual(len(_decompress_kanban_cards(second_page["cards"])), 1)

	def test_private_board_blocks_other_users(self):
		from frappe.desk.doctype.kanban_board.kanban_board import (
			add_card,
			get_card_config,
			get_kanban_board_context,
			update_order,
			update_order_for_single_card,
		)

		other = "kanban_perm_test@example.com"
		if not frappe.db.exists("User", other):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": other,
					"first_name": "Kanban",
					"last_name": "Perm",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)

		# Board is private and owned by the test session user, not `other`.
		frappe.set_user(other)
		self.assertRaises(frappe.PermissionError, lambda: get_card_config(self.board_name))
		self.assertRaises(frappe.PermissionError, lambda: get_kanban_board_context(self.board_name))
		self.assertRaises(
			frappe.PermissionError,
			lambda: update_order_for_single_card(
				board_name=self.board_name,
				docname=self.todos[0],
				from_colname="Open",
				to_colname="Closed",
				from_order=[],
				to_order=[self.todos[0]],
			),
		)
		self.assertRaises(
			frappe.PermissionError,
			lambda: update_order(self.board_name, {"Open": self.todos[:3]}),
		)
		self.assertRaises(
			frappe.PermissionError,
			lambda: add_card(self.board_name, self.todos[0], "Open"),
		)
		frappe.set_user("Administrator")

	def test_private_toggle_allowed_only_for_owner_or_admin(self):
		other = "kanban_perm_test@example.com"
		if not frappe.db.exists("User", other):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": other,
					"first_name": "Kanban",
					"last_name": "Perm",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)

		# Non-owner cannot toggle Private.
		frappe.set_user(other)
		board = frappe.get_doc("Kanban Board", self.board_name)
		board.private = 0
		self.assertRaises(frappe.PermissionError, board.save, ignore_permissions=True)

		# Owner (Administrator in this test fixture) can toggle Private.
		frappe.set_user("Administrator")
		board = frappe.get_doc("Kanban Board", self.board_name)
		board.private = 0
		board.save(ignore_permissions=True)
		self.assertEqual(cint(frappe.db.get_value("Kanban Board", self.board_name, "private")), 0)

		# Administrator can toggle it back as well.
		board.reload()
		board.private = 1
		board.save(ignore_permissions=True)
		self.assertEqual(cint(frappe.db.get_value("Kanban Board", self.board_name, "private")), 1)

	def test_standard_board_blocks_non_admin_edits(self):
		other = "kanban_perm_test@example.com"
		if not frappe.db.exists("User", other):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": other,
					"first_name": "Kanban",
					"last_name": "Perm",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)

		frappe.db.set_value("Kanban Board", self.board_name, "is_standard", "Yes")
		try:
			frappe.set_user(other)
			board = frappe.get_doc("Kanban Board", self.board_name)
			board.use_kanban_v2 = 1 if not cint(board.use_kanban_v2) else 0
			self.assertRaises(frappe.ValidationError, board.save, ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_value("Kanban Board", self.board_name, "is_standard", "No")

	def test_standard_board_requires_developer_mode(self):
		frappe.set_user("Administrator")
		board = frappe.get_doc("Kanban Board", self.board_name)
		old_dev_mode = getattr(frappe.local.conf, "developer_mode", 0)
		try:
			frappe.local.conf.developer_mode = 0
			board.is_standard = "Yes"
			self.assertRaises(frappe.ValidationError, board.save, ignore_permissions=True)
		finally:
			frappe.local.conf.developer_mode = old_dev_mode

	def test_standard_board_delete_blocked_outside_developer_mode(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Kanban Board", self.board_name, "is_standard", "Yes")
		old_dev_mode = getattr(frappe.local.conf, "developer_mode", 0)
		try:
			frappe.local.conf.developer_mode = 0
			self.assertRaises(
				frappe.ValidationError,
				frappe.delete_doc,
				"Kanban Board",
				self.board_name,
			)
		finally:
			frappe.local.conf.developer_mode = old_dev_mode
			frappe.db.set_value("Kanban Board", self.board_name, "is_standard", "No")

	def test_group_by_fields_seeded_with_select_fields(self):
		name = frappe.generate_hash(length=10)
		board = frappe.get_doc(
			{
				"doctype": "Kanban Board",
				"kanban_board_name": name,
				"reference_doctype": "ToDo",
				"field_name": "status",
				"columns": [{"column_name": "Open"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("Kanban Board", board.name, force=1))

		meta = frappe.get_meta("ToDo")
		seeded = {f.fieldname for f in board.group_by_fields}
		# Every seeded field is a non-hidden Select…
		for fieldname in seeded:
			self.assertEqual(meta.get_field(fieldname).fieldtype, "Select")
		# …the column field (status) is excluded, and other Select fields are in.
		self.assertNotIn("status", seeded)
		self.assertIn("priority", seeded)

	def test_get_kanban_group_values(self):
		from frappe.desk.doctype.kanban_board.kanban_board import get_kanban_group_values

		# priority is seeded into group_by_fields; status (column field) is not.
		for name, priority in zip(self.todos, ["High", "High", "High", "Medium"], strict=True):
			frappe.db.set_value("ToDo", name, "priority", priority)

		res = get_kanban_group_values(self.board_name, "priority")
		lanes = {lane["value"]: lane["count"] for lane in res["lanes"]}
		self.assertEqual(lanes.get("High"), 3)
		self.assertEqual(lanes.get("Medium"), 1)
		self.assertEqual(res["unset"], 0)

		# Group by _assign: none are assigned, so everything is in the not-set bucket.
		res_assign = get_kanban_group_values(self.board_name, "_assign")
		self.assertEqual(res_assign["lanes"], [])
		self.assertEqual(res_assign["unset"], 4)

	def test_get_kanban_group_values_rejects_unconfigured_field(self):
		from frappe.desk.doctype.kanban_board.kanban_board import get_kanban_group_values

		# Column field and other DocType fields are not groupable unless listed.
		self.assertRaises(frappe.ValidationError, get_kanban_group_values, self.board_name, "status")
		self.assertRaises(frappe.ValidationError, get_kanban_group_values, self.board_name, "owner")
		self.assertRaises(frappe.ValidationError, get_kanban_group_values, self.board_name, "nope")

	def test_get_kanban_column_order_and_index_invalid_column(self):
		board = frappe.get_doc("Kanban Board", self.board_name)
		self.assertRaises(frappe.ValidationError, get_kanban_column_order_and_index, board, "Not A Column")

	def test_group_by_fields_not_reseeded_when_configured(self):
		name = frappe.generate_hash(length=10)
		board = frappe.get_doc(
			{
				"doctype": "Kanban Board",
				"kanban_board_name": name,
				"reference_doctype": "ToDo",
				"field_name": "status",
				"columns": [{"column_name": "Open"}],
				"group_by_fields": [{"fieldname": "priority", "label": "Priority"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("Kanban Board", board.name, force=1))
		self.assertEqual([f.fieldname for f in board.group_by_fields], ["priority"])


class TestKanbanBoardNativePayloads(IntegrationTestCase):
	def setUp(self):
		self.board = kb.quick_kanban_board("ToDo", frappe.generate_hash(length=10), "status")

	def tearDown(self):
		frappe.delete_doc("Kanban Board", self.board.name, force=True)

	def test_endpoints_accept_native_payloads(self):
		# update_column_order with a native list (frappe.parse_json passthrough)
		kb.update_column_order(self.board.name, [c.column_name for c in self.board.columns])

		# save_settings with a native dict (partial payload must not KeyError)
		resp = kb.save_settings(self.board.name, {"fields": []})
		self.assertEqual(resp["doctype"], "Kanban Board")
		resp = kb.save_settings(self.board.name, {"fields": [], "show_labels": 0})
		self.assertEqual(resp["doctype"], "Kanban Board")

		# update_order with a native dict
		_board, updated_cards = kb.update_order(self.board.name, {})
		self.assertEqual(updated_cards, [])
