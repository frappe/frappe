import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.form import linked_with
from frappe.tests.utils import FrappeTestCase


class TestLinkedWith(FrappeTestCase):
	def setUp(self):
		parent_doctype = new_doctype("Parent DocType")
		parent_doctype.is_submittable = 1
		parent_doctype.insert()

		child_doctype1 = new_doctype(
			"Child DocType1",
			fields=[
				{
					"label": "Parent DocType",
					"fieldname": "parent_doctype",
					"fieldtype": "Link",
					"options": "Parent DocType",
				},
				{
					"label": "Reference field",
					"fieldname": "reference_name",
					"fieldtype": "Dynamic Link",
					"options": "reference_doctype",
				},
				{
					"label": "Reference Doctype",
					"fieldname": "reference_doctype",
					"fieldtype": "Link",
					"options": "DocType",
				},
			],
			unique=0,
		)
		child_doctype1.is_submittable = 1
		child_doctype1.insert()

		child_doctype2 = new_doctype(
			"Child DocType2",
			fields=[
				{
					"label": "Parent DocType",
					"fieldname": "parent_doctype",
					"fieldtype": "Link",
					"options": "Parent DocType",
				},
				{
					"label": "Child DocType1",
					"fieldname": "child_doctype1",
					"fieldtype": "Link",
					"options": "Child DocType1",
				},
			],
			unique=0,
		)
		child_doctype2.is_submittable = 1
		child_doctype2.insert()

	def tearDown(self):
		for doctype in ["Parent DocType", "Child DocType1", "Child DocType2"]:
			frappe.delete_doc("DocType", doctype)

	def test_get_doctype_references_by_link_field(self):
		references = linked_with.get_references_across_doctypes_by_link_field(
			to_doctypes=["Parent DocType"]
		)
		self.assertEqual(len(references["Parent DocType"]), 3)
		self.assertIn(
			{"doctype": "Child DocType1", "fieldname": "parent_doctype"}, references["Parent DocType"]
		)
		self.assertIn(
			{"doctype": "Child DocType2", "fieldname": "parent_doctype"}, references["Parent DocType"]
		)

		references = linked_with.get_references_across_doctypes_by_link_field(
			to_doctypes=["Child DocType1"]
		)
		self.assertEqual(len(references["Child DocType1"]), 2)
		self.assertIn(
			{"doctype": "Child DocType2", "fieldname": "child_doctype1"}, references["Child DocType1"]
		)

		references = linked_with.get_references_across_doctypes_by_link_field(
			to_doctypes=["Child DocType1", "Parent DocType"], limit_link_doctypes=["Child DocType1"]
		)
		self.assertEqual(len(references["Child DocType1"]), 1)
		self.assertEqual(len(references["Parent DocType"]), 1)
		self.assertIn(
			{"doctype": "Child DocType1", "fieldname": "parent_doctype"}, references["Parent DocType"]
		)

	def test_get_doctype_references_by_dlink_field(self):
		references = linked_with.get_references_across_doctypes_by_dynamic_link_field(
			to_doctypes=["Parent DocType"],
			limit_link_doctypes=["Parent DocType", "Child DocType1", "Child DocType2"],
		)
		self.assertFalse(references)

		parent_record = frappe.get_doc({"doctype": "Parent DocType"}).insert()

		child_record = frappe.get_doc(
			{
				"doctype": "Child DocType1",
				"reference_doctype": "Parent DocType",
				"reference_name": parent_record.name,
			}
		).insert()

		references = linked_with.get_references_across_doctypes_by_dynamic_link_field(
			to_doctypes=["Parent DocType"],
			limit_link_doctypes=["Parent DocType", "Child DocType1", "Child DocType2"],
		)

		self.assertEqual(len(references["Parent DocType"]), 1)
		self.assertEqual(references["Parent DocType"][0]["doctype"], "Child DocType1")
		self.assertEqual(references["Parent DocType"][0]["doctype_fieldname"], "reference_doctype")

		child_record.delete()
		parent_record.delete()

	def test_get_submitted_linked_docs(self):
		parent_record = frappe.get_doc({"doctype": "Parent DocType"}).insert()

		child_record = frappe.get_doc(
			{
				"doctype": "Child DocType1",
				"reference_doctype": "Parent DocType",
				"reference_name": parent_record.name,
				"docstatus": 1,
			}
		).insert()

		linked_docs = linked_with.get_submitted_linked_docs(parent_record.doctype, parent_record.name)[
			"docs"
		]
		self.assertIn(child_record.name, linked_docs[0]["name"])
		child_record.cancel()
		child_record.delete()
		parent_record.delete()
