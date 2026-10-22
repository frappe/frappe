from io import BytesIO

import frappe
from frappe.gettext.extractors.doctype import extract
from frappe.tests.utils import FrappeTestCase


class TestDocType(FrappeTestCase):
	def test_extract_line_numbers(self):
		doctype_json = frappe.as_json(
			{
				"doctype": "DocType",
				"name": "Test Ticket",
				"fields": [
					{
						"fieldname": "status",
						"fieldtype": "Select",
						"label": "Status",
						"description": "Ticket",
						"options": "Open\nClosed",
					},
					{"fieldname": "ticket", "fieldtype": "Data", "label": "Ticket"},
				],
				"permissions": [{"role": "System Manager"}],
			}
		)
		lines = doctype_json.splitlines()

		def line_of(snippet):
			return next(i for i, line in enumerate(lines, start=1) if snippet in line)

		messages = [
			(lineno, message)
			for lineno, _funcname, message, _comments in extract(BytesIO(doctype_json.encode()))
		]

		self.assertEqual(
			messages,
			[
				(line_of('"name": "Test Ticket"'), "Test Ticket"),
				(line_of('"label": "Status"'), "Status"),
				(line_of('"description": "Ticket"'), "Ticket"),
				(line_of('"options": "Open\\nClosed"'), "Open"),
				(line_of('"options": "Open\\nClosed"'), "Closed"),
				(line_of('"label": "Ticket"'), "Ticket"),
				(line_of('"role": "System Manager"'), "System Manager"),
			],
		)
