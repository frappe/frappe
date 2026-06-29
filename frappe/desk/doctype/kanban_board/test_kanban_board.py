# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.doctype.kanban_board import kanban_board as kb
from frappe.tests import IntegrationTestCase


class TestKanbanBoard(IntegrationTestCase):
	def setUp(self):
		self.board = kb.quick_kanban_board("ToDo", frappe.generate_hash(length=10), "status")

	def tearDown(self):
		frappe.delete_doc("Kanban Board", self.board.name, force=True)

	def test_endpoints_accept_native_payloads(self):
		# update_column_order with a native list (frappe.parse_json passthrough)
		kb.update_column_order(self.board.name, [c.column_name for c in self.board.columns])

		# save_settings with a native dict
		resp = kb.save_settings(self.board.name, {"fields": [], "show_labels": 0})
		self.assertEqual(resp["doctype"], "Kanban Board")

		# update_order with a native dict
		_board, updated_cards = kb.update_order(self.board.name, {})
		self.assertEqual(updated_cards, [])
