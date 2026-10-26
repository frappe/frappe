import json
from io import BytesIO

import frappe
from frappe.gettext.extractors.workspace import extract
from frappe.tests import UnitTestCase


class TestWorkspace(UnitTestCase):
	def test_role_layouts_are_extracted(self):
		workspace = {
			"doctype": "Workspace",
			"label": "Lending",
			"content": json.dumps([{"type": "header", "data": {"text": "Loans"}}]),
			"charts": [{"label": "Disbursed"}],
		}
		plain = [(message, comments) for _l, _f, message, comments in extract(as_file(workspace))]

		workspace["variants"] = [
			{
				"role": "Credit Manager",
				"content": json.dumps([{"type": "header", "data": {"text": "Approvals"}}]),
				"widgets": json.dumps({"card": [{"label": "Credit Reports", "links": "[]"}]}),
			}
		]
		messages = [(message, comments) for _l, _f, message, comments in extract(as_file(workspace))]

		self.assertEqual(messages[: len(plain)], plain)
		self.assertIn(
			("Credit Reports", ["Label of a Card Break in the Lending Workspace (Credit Manager layout)"]),
			messages,
		)
		self.assertIn(
			("Approvals", ["Header text in the Lending Workspace (Credit Manager layout)"]), messages
		)


def as_file(doc):
	return BytesIO(frappe.as_json(doc).encode())
