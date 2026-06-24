# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.kanban_board.kanban_board import (
	get_kanban_column_order_and_index,
	update_order,
	update_order_for_single_card,
)
from frappe.tests import IntegrationTestCase


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
