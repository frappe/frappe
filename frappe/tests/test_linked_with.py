import random
import string

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.database import savepoint
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
			frappe.db.commit()

	def test_get_doctype_references_by_link_field(self):
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

		linked_docs = linked_with.get_submitted_linked_docs(parent_record.doctype, parent_record.name)["docs"]
		self.assertIn(child_record.name, linked_docs[0]["name"])
		child_record.cancel()
		child_record.delete()
		parent_record.delete()

	def test_check_delete_integrity(self):
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

	def test_reserved_keywords(self):
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

	def test_virtual_link_fields_excluded_from_references(self):
		"""Virtual Link fields should not be included in references.

		Virtual fields do not have database columns, so including them in
		reference queries would cause database errors when the system tries
		to filter by these non-existent columns.
		"""
		dt_name = "Test " + "".join(random.sample(string.ascii_lowercase, 10))
		target_dt_name = "Test Target " + "".join(random.sample(string.ascii_lowercase, 10))

		# Create a target DocType that the Link fields will reference
		target_doctype = new_doctype(target_dt_name)
		target_doctype.insert()

		# Create a DocType with both regular and virtual Link fields
		doctype_with_virtual = new_doctype(
			dt_name,
			fields=[
				{
					"label": "Regular Link",
					"fieldname": "regular_link",
					"fieldtype": "Link",
					"options": target_dt_name,
					"is_virtual": 0,
				},
				{
					"label": "Virtual Link",
					"fieldname": "virtual_link",
					"fieldtype": "Link",
					"options": target_dt_name,
					"is_virtual": 1,
				},
			],
		)
		doctype_with_virtual.insert()

		try:
			references = linked_with.get_references_across_doctypes_by_link_field(
				to_doctypes=[target_dt_name]
			)

			# Should only contain the regular link, not the virtual one
			self.assertIn(target_dt_name, references)
			fieldnames = [ref["fieldname"] for ref in references[target_dt_name]]

			self.assertIn("regular_link", fieldnames)
			self.assertNotIn(
				"virtual_link",
				fieldnames,
				"Virtual Link fields should not be included in references",
			)
		finally:
			frappe.delete_doc("DocType", dt_name)
			frappe.delete_doc("DocType", target_dt_name)
			frappe.db.commit()
