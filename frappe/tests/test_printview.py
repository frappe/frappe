import json

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.tests import IntegrationTestCase
from frappe.www.printview import get_html_and_style


class PrintViewTest(IntegrationTestCase):
	def test_print_view_without_errors(self):
		user = frappe.get_last_doc("User")

		messages_before = frappe.get_message_log()
		ret = get_html_and_style(doc=user.as_json(), print_format="Standard", no_letterhead=1)
		messages_after = frappe.get_message_log()

		if len(messages_after) > len(messages_before):
			new_messages = messages_after[len(messages_before) :]
			self.fail("Print view showing error/warnings: \n" + "\n".join(str(msg) for msg in new_messages))

		# html should exist
		self.assertTrue(bool(ret["html"]))

	def test_print_error(self):
		"""Print failures shouldn't generate PDF with failure message but instead escalate the error"""
		doctype = new_doctype(is_submittable=1).insert()

		doc = frappe.new_doc(doctype.name)
		doc.insert()
		doc.submit()
		doc.cancel()

		# cancelled doc can't be printed by default
		self.assertRaises(frappe.PermissionError, frappe.attach_print, doc.doctype, doc.name)


_PARENT_MARKER = "PARENTVIRT_hello"
_CHILD_MARKER = "CHILDVIRT_5"


class PrintVirtualFieldTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		cls.child_dt = new_doctype(
			istable=1,
			fields=[
				{"label": "Code", "fieldname": "code", "fieldtype": "Data"},
				{
					"label": "Child Virtual",
					"fieldname": "cvirt",
					"fieldtype": "Data",
					"is_virtual": 1,
					"options": "'CHILDVIRT_' + (doc.code or '')",
				},
			],
		).insert(ignore_permissions=True)
		cls.addClassCleanup(cls.child_dt.delete, ignore_permissions=True)

		cls.parent_dt = new_doctype(
			fields=[
				{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				{
					"label": "Parent Virtual",
					"fieldname": "pvirt",
					"fieldtype": "Data",
					"is_virtual": 1,
					"options": "'PARENTVIRT_' + (doc.title or '')",
				},
				{
					"label": "Items",
					"fieldname": "items",
					"fieldtype": "Table",
					"options": cls.child_dt.name,
				},
			],
		).insert(ignore_permissions=True)
		cls.addClassCleanup(cls.parent_dt.delete, ignore_permissions=True)

	def _make_doc(self):
		return frappe.get_doc(
			{"doctype": self.parent_dt.name, "title": "hello", "items": [{"code": "5"}]}
		).insert(ignore_permissions=True)

	def _make_beta_print_format(self):
		"""Print Format Builder (beta) format showing the parent virtual field and a
		child-table column bound to the child virtual field."""
		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test VFP {frappe.generate_hash(length=6)}",
				"doc_type": self.parent_dt.name,
				"print_format_builder_beta": 1,
				"custom_format": 0,
				"standard": "No",
				"format_data": json.dumps(
					{
						"sections": [
							{
								"label": "",
								"columns": [
									{
										"label": "",
										"fields": [
											{
												"fieldtype": "Data",
												"fieldname": "pvirt",
												"label": "Parent Virtual",
											},
											{
												"fieldtype": "Table",
												"fieldname": "items",
												"label": "Items",
												"options": self.child_dt.name,
												"table_columns": [
													{
														"fieldtype": "Data",
														"fieldname": "cvirt",
														"label": "Child Virtual",
														"width": 100,
													}
												],
											},
										],
									}
								],
							}
						],
						"header": {"columns": [{"label": "", "fields": []}]},
						"footer": {"columns": [{"label": "", "fields": []}]},
					}
				),
			}
		)
		pf.insert(ignore_permissions=True)
		self.addCleanup(pf.delete, ignore_permissions=True)
		return pf

	def test_resolve_virtual_fields_materializes_parent_and_children(self):
		doc = self._make_doc()
		fresh = frappe.get_doc(self.parent_dt.name, doc.name)

		# Fresh DB load: virtual fields are not materialized on parent or child.
		self.assertIsNone(fresh.get("pvirt"))
		self.assertIsNone(fresh.items[0].get("cvirt"))

		fresh.resolve_virtual_fields()

		self.assertEqual(fresh.get("pvirt"), _PARENT_MARKER)
		self.assertEqual(fresh.items[0].get("cvirt"), _CHILD_MARKER)

	def test_standard_print_renders_virtual_fields(self):
		doc = self._make_doc()
		# Passing doctype+name strings forces get_lazy_doc (the fresh-load path), NOT
		# the frm.doc round-trip that already works.
		ret = get_html_and_style(
			doc=self.parent_dt.name, name=doc.name, print_format="Standard", no_letterhead=1
		)
		self.assertIn(_PARENT_MARKER, ret["html"])
		self.assertIn(_CHILD_MARKER, ret["html"])

	def test_beta_print_renders_virtual_fields(self):
		from frappe.utils.print_format_generator import get_html

		doc = self._make_doc()
		pf = self._make_beta_print_format()

		html = get_html(self.parent_dt.name, doc.name, pf.name)
		self.assertIn(_PARENT_MARKER, html)
		self.assertIn(_CHILD_MARKER, html)

	def test_resolve_virtual_fields_is_idempotent(self):
		doc = self._make_doc()
		doc.pvirt = "PRESET_PARENT"
		doc.items[0].cvirt = "PRESET_CHILD"

		doc.resolve_virtual_fields()

		# Only None fields are touched; already-present values survive.
		self.assertEqual(doc.get("pvirt"), "PRESET_PARENT")
		self.assertEqual(doc.items[0].get("cvirt"), "PRESET_CHILD")
