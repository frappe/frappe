import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.form import linked_with
from frappe.tests.utils import FrappeTestCase


class TestLinkedWith(FrappeTestCase):
	def setUp(self):
		parent_doc = new_doctype("Parent Doc")
		parent_doc.is_submittable = 1
		parent_doc.insert()

		child_doc1 = new_doctype(
			"Child Doc1",
			fields=[
				{
					"label": "Parent Doc",
					"fieldname": "parent_doc",
					"fieldtype": "Link",
					"options": "Parent Doc",
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
		child_doc1.is_submittable = 1
		child_doc1.insert()

		child_doc2 = new_doctype(
			"Child Doc2",
			fields=[
				{
					"label": "Parent Doc",
					"fieldname": "parent_doc",
					"fieldtype": "Link",
					"options": "Parent Doc",
				},
				{
					"label": "Child Doc1",
					"fieldname": "child_doc1",
					"fieldtype": "Link",
					"options": "Child Doc1",
				},
			],
			unique=0,
		)
		child_doc2.is_submittable = 1
		child_doc2.insert()

	def tearDown(self):
		for doctype in ["Parent Doc", "Child Doc1", "Child Doc2"]:
			frappe.delete_doc("DocType", doctype)

	def test_get_doctype_references_by_link_field(self):
		references = linked_with.get_references_across_doctypes_by_link_field(to_doctypes=["Parent Doc"])
		self.assertEqual(len(references["Parent Doc"]), 3)
		self.assertIn({"doctype": "Child Doc1", "fieldname": "parent_doc"}, references["Parent Doc"])
		self.assertIn({"doctype": "Child Doc2", "fieldname": "parent_doc"}, references["Parent Doc"])

		references = linked_with.get_references_across_doctypes_by_link_field(to_doctypes=["Child Doc1"])
		self.assertEqual(len(references["Child Doc1"]), 2)
		self.assertIn({"doctype": "Child Doc2", "fieldname": "child_doc1"}, references["Child Doc1"])

		references = linked_with.get_references_across_doctypes_by_link_field(
			to_doctypes=["Child Doc1", "Parent Doc"], limit_link_doctypes=["Child Doc1"]
		)
		self.assertEqual(len(references["Child Doc1"]), 1)
		self.assertEqual(len(references["Parent Doc"]), 1)
		self.assertIn({"doctype": "Child Doc1", "fieldname": "parent_doc"}, references["Parent Doc"])

	def test_get_doctype_references_by_dlink_field(self):
		references = linked_with.get_references_across_doctypes_by_dynamic_link_field(
			to_doctypes=["Parent Doc"], limit_link_doctypes=["Parent Doc", "Child Doc1", "Child Doc2"]
		)
		self.assertFalse(references)

		parent_record = frappe.get_doc({"doctype": "Parent Doc"}).insert()

		child_record = frappe.get_doc(
			{
				"doctype": "Child Doc1",
				"reference_doctype": "Parent Doc",
				"reference_name": parent_record.name,
			}
		).insert()

		references = linked_with.get_references_across_doctypes_by_dynamic_link_field(
			to_doctypes=["Parent Doc"], limit_link_doctypes=["Parent Doc", "Child Doc1", "Child Doc2"]
		)

		self.assertEqual(len(references["Parent Doc"]), 1)
		self.assertEqual(references["Parent Doc"][0]["doctype"], "Child Doc1")
		self.assertEqual(references["Parent Doc"][0]["doctype_fieldname"], "reference_doctype")

		child_record.delete()
		parent_record.delete()

	def test_get_submitted_linked_docs(self):
		parent_record = frappe.get_doc({"doctype": "Parent Doc"}).insert()

		child_record = frappe.get_doc(
			{
				"doctype": "Child Doc1",
				"reference_doctype": "Parent Doc",
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
