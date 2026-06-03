# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

# A simple, stable DocType available in every Frappe install
TEST_DOCTYPE = "ToDo"


class TestDocTypeLayout(IntegrationTestCase):
	def setUp(self):
		# Remove any leftover test layouts from a previous run
		for name in frappe.get_all("DocType Layout", filters={"title": ["like", "_Test%"]}, pluck="name"):
			frappe.delete_doc("DocType Layout", name, force=True, ignore_permissions=True)

	def _make_layout(self, title="_Test Layout", document_type=TEST_DOCTYPE, **kwargs):
		doc = frappe.get_doc(
			{"doctype": "DocType Layout", "title": title, "document_type": document_type, **kwargs}
		)
		doc.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "DocType Layout", doc.name, force=True, ignore_permissions=True)
		return doc

	def test_sync_fields_populates_all_fields_for_new_layout(self):
		"""sync_fields on an unsaved layout adds every field from the DocType."""
		doc = frappe.new_doc("DocType Layout")
		doc.title = "_Test Layout"
		doc.document_type = TEST_DOCTYPE

		result = doc.sync_fields()

		meta_fieldnames = {f.fieldname for f in frappe.get_meta(TEST_DOCTYPE, cached=False).fields}
		layout_fieldnames = {f.fieldname for f in doc.fields}
		self.assertIsNotNone(result)
		self.assertEqual(meta_fieldnames, layout_fieldnames)
		self.assertEqual(result["removed"], [])
		self.assertEqual(len(result["added"]), len(meta_fieldnames))

	def test_sync_fields_returns_none_when_already_up_to_date(self):
		"""sync_fields returns None when the layout already matches the DocType."""
		doc = self._make_layout()
		doc.sync_fields()
		doc.save()
		doc.reload()

		result = doc.sync_fields()

		self.assertIsNone(result)

	def test_sync_fields_detects_field_added_to_doctype(self):
		"""A field missing from the layout is reported as added by sync_fields."""
		doc = self._make_layout()
		doc.sync_fields()
		doc.save()
		doc.reload()

		# Simulate a new DocType field by dropping one row from the layout
		removed_fieldname = doc.fields[0].fieldname
		doc.fields = [f for f in doc.fields if f.fieldname != removed_fieldname]
		doc.save()
		doc.reload()

		result = doc.sync_fields()

		self.assertIsNotNone(result)
		self.assertIn(removed_fieldname, [f["fieldname"] for f in result["added"]])

	def test_sync_fields_detects_field_removed_from_doctype(self):
		"""A layout row whose fieldname no longer exists in the DocType is reported as removed."""
		doc = self._make_layout()
		doc.sync_fields()
		doc.append("fields", {"fieldname": "_nonexistent_xyz", "label": "Ghost Field"})
		doc.save()
		doc.reload()

		result = doc.sync_fields()

		self.assertIsNotNone(result)
		self.assertIn("_nonexistent_xyz", [f["fieldname"] for f in result["removed"]])

	def test_validate_rejects_based_on_from_different_doctype(self):
		"""based_on must reference a layout for the same document_type."""
		other = self._make_layout("_Test Other Layout", document_type="User")

		with self.assertRaises(frappe.ValidationError):
			self._make_layout("_Test Child Layout", based_on=other.name)

	def test_validate_accepts_based_on_from_same_doctype(self):
		"""based_on is valid when it references a layout for the same document_type."""
		parent = self._make_layout("_Test Parent Layout")
		# Should not raise
		self._make_layout("_Test Child Layout", based_on=parent.name)

	def test_validate_rejects_standard_layout_outside_developer_mode(self):
		"""Saving a standard layout without developer mode must raise PermissionError."""
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			doc = frappe.get_doc(
				{
					"doctype": "DocType Layout",
					"title": "_Test Std Layout",
					"document_type": TEST_DOCTYPE,
					"is_standard": 1,
				}
			)
			with self.assertRaises(frappe.PermissionError):
				doc.insert(ignore_permissions=True)
