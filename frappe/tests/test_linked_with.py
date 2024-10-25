import random
import string

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.database import savepoint
from frappe.desk.form import linked_with
from frappe.tests import IntegrationTestCase


class TestLinkedWith(IntegrationTestCase):
	def setUp(self) -> None:
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

	def tearDown(self) -> None:
		for doctype in ["Parent DocType", "Child DocType1", "Child DocType2"]:
			frappe.delete_doc("DocType", doctype)
			frappe.db.commit()

	def test_get_doctype_references_by_link_field(self) -> None:
		references = linked_with.get_references_across_doctypes_by_link_field(to_doctypes=["Parent DocType"])
		self.assertEqual(len(references["Parent DocType"]), 3)
		self.assertIn(
			{"doctype": "Child DocType1", "fieldname": "parent_doctype"}, references["Parent DocType"]
		)
		self.assertIn(
			{"doctype": "Child DocType2", "fieldname": "parent_doctype"}, references["Parent DocType"]
		)

		references = linked_with.get_references_across_doctypes_by_link_field(to_doctypes=["Child DocType1"])
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

	def test_get_doctype_references_by_dlink_field(self) -> None:
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

	def test_get_submitted_linked_docs(self) -> None:
		parent_record = frappe.get_doc({"doctype": "Parent DocType"}).insert()

		child_record = frappe.get_doc(
			{
				"doctype": "Child DocType1",
				"reference_doctype": "Parent DocType",
				"reference_name": parent_record.name,
				"docstatus": 1,
			}
		).insert()

		linked_docs = linked_with.get_submitted_linked_docs(parent_record.doctype, parent_record.name)["docs"]
		self.assertIn(child_record.name, linked_docs[0]["name"])
		child_record.cancel()
		child_record.delete()
		parent_record.delete()

	def test_check_delete_integrity(self) -> None:
		"""Don't allow deleting cancelled document if amendment exists"""
		doc = frappe.get_doc({"doctype": "Parent DocType"}).insert()
		doc.submit()
		doc.cancel()

		amendment = frappe.copy_doc(doc)
		amendment.amended_from = doc.name
		amendment.docstatus = 0
		amendment.insert()
		amendment.submit()

		self.assertRaises(frappe.LinkExistsError, doc.delete)

	def test_reserved_keywords(self) -> None:
		dt_name = "Test " + "".join(random.sample(string.ascii_lowercase, 10))
		new_doctype(
			dt_name,
			fields=[
				{
					"fieldname": "from",
					"fieldtype": "Link",
					"options": "DocType",
				},
				{
					"fieldname": "order",
					"fieldtype": "Dynamic Link",
					"options": "from",
				},
			],
			is_submittable=True,
		).insert()

		linked_doc = frappe.new_doc(dt_name).insert().submit()

		second_doc = (
			frappe.new_doc(dt_name, **{"from": linked_doc.doctype, "order": linked_doc.name})
			.insert()
			.submit()
		)

		with savepoint(frappe.LinkExistsError):
			linked_doc.cancel() and self.fail("Cancellation shouldn't have worked")

		second_doc.cancel()
		linked_doc.reload().cancel()
