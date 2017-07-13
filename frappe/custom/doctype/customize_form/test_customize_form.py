# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, unittest, json
from frappe.test_runner import make_test_records_for_doctype
from frappe.core.doctype.doctype.doctype import InvalidFieldNameError

test_dependencies = ["Custom Field", "Property Setter"]
class TestCustomizeForm(unittest.TestCase):
	def insert_custom_field(self):
		frappe.delete_doc_if_exists("Custom Field", "User-test_custom_field")
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "User",
			"label": "Test Custom Field",
			"description": "A Custom Field for Testing",
			"fieldtype": "Select",
			"in_list_view": 1,
			"options": "\nCustom 1\nCustom 2\nCustom 3",
			"default": "Custom 3",
			"insert_after": frappe.get_meta('User').fields[-1].fieldname
		}).insert()

	def setUp(self):
		self.insert_custom_field()
		frappe.db.commit()
		frappe.clear_cache(doctype="User")

	def tearDown(self):
		frappe.delete_doc("Custom Field", "User-test_custom_field")
		frappe.db.commit()
		frappe.clear_cache(doctype="User")

	def get_customize_form(self, doctype=None):
		d = frappe.get_doc("Customize Form")
		if doctype:
			d.doc_type = doctype
		d.run_method("fetch_to_customize")
		return d

	def test_fetch_to_customize(self):
		d = self.get_customize_form()
		self.assertEquals(d.doc_type, None)
		self.assertEquals(len(d.get("fields")), 0)

		d = self.get_customize_form("Event")
		self.assertEquals(d.doc_type, "Event")
		self.assertEquals(len(d.get("fields")), 29)

		d = self.get_customize_form("User")
		self.assertEquals(d.doc_type, "User")

		self.assertEquals(len(d.get("fields")),
			len(frappe.get_doc("DocType", d.doc_type).fields) + 1)
		self.assertEquals(d.get("fields")[-1].fieldname, "test_custom_field")
		self.assertEquals(d.get("fields", {"fieldname": "location"})[0].in_list_view, 1)

		return d

	def test_save_customization_property(self):
		d = self.get_customize_form("User")
		self.assertEquals(frappe.db.get_value("Property Setter",
			{"doc_type": "User", "property": "allow_copy"}, "value"), None)

		d.allow_copy = 1
		d.run_method("save_customization")
		self.assertEquals(frappe.db.get_value("Property Setter",
			{"doc_type": "User", "property": "allow_copy"}, "value"), '1')

		d.allow_copy = 0
		d.run_method("save_customization")
		self.assertEquals(frappe.db.get_value("Property Setter",
			{"doc_type": "User", "property": "allow_copy"}, "value"), None)

	def test_save_customization_field_property(self):
		d = self.get_customize_form("User")
		self.assertEquals(frappe.db.get_value("Property Setter",
			{"doc_type": "User", "property": "reqd", "field_name": "location"}, "value"), None)

		location_field = d.get("fields", {"fieldname": "location"})[0]
		location_field.reqd = 1
		d.run_method("save_customization")
		self.assertEquals(frappe.db.get_value("Property Setter",
			{"doc_type": "User", "property": "reqd", "field_name": "location"}, "value"), '1')

		location_field = d.get("fields", {"fieldname": "location"})[0]
		location_field.reqd = 0
		d.run_method("save_customization")
		self.assertEquals(frappe.db.get_value("Property Setter",
			{"doc_type": "User", "property": "reqd", "field_name": "location"}, "value"), None)

	def test_save_customization_custom_field_property(self):
		d = self.get_customize_form("User")
		self.assertEquals(frappe.db.get_value("Custom Field", "User-test_custom_field", "reqd"), 0)

		custom_field = d.get("fields", {"fieldname": "test_custom_field"})[0]
		custom_field.reqd = 1
		d.run_method("save_customization")
		self.assertEquals(frappe.db.get_value("Custom Field", "User-test_custom_field", "reqd"), 1)

		custom_field = d.get("fields", {"is_custom_field": True})[0]
		custom_field.reqd = 0
		d.run_method("save_customization")
		self.assertEquals(frappe.db.get_value("Custom Field", "User-test_custom_field", "reqd"), 0)

	def test_save_customization_new_field(self):
		d = self.get_customize_form("User")
		last_fieldname = d.fields[-1].fieldname
		d.append("fields", {
			"label": "Test Add Custom Field Via Customize Form",
			"fieldtype": "Data",
			"is_custom_field": 1
		})
		d.run_method("save_customization")
		self.assertEquals(frappe.db.get_value("Custom Field",
			"User-test_add_custom_field_via_customize_form", "fieldtype"), "Data")

		self.assertEquals(frappe.db.get_value("Custom Field",
			"User-test_add_custom_field_via_customize_form", 'insert_after'), last_fieldname)

		frappe.delete_doc("Custom Field", "User-test_add_custom_field_via_customize_form")
		self.assertEquals(frappe.db.get_value("Custom Field",
			"User-test_add_custom_field_via_customize_form"), None)


	def test_save_customization_remove_field(self):
		d = self.get_customize_form("User")
		custom_field = d.get("fields", {"fieldname": "test_custom_field"})[0]
		d.get("fields").remove(custom_field)
		d.run_method("save_customization")

		self.assertEquals(frappe.db.get_value("Custom Field", custom_field.name), None)

		frappe.local.test_objects["Custom Field"] = []
		make_test_records_for_doctype("Custom Field")

	def test_reset_to_defaults(self):
		d = frappe.get_doc("Customize Form")
		d.doc_type = "User"
		d.run_method('reset_to_defaults')

		self.assertEquals(d.get("fields", {"fieldname": "location"})[0].in_list_view, 0)

		frappe.local.test_objects["Property Setter"] = []
		make_test_records_for_doctype("Property Setter")

	def test_set_allow_on_submit(self):
		d = self.get_customize_form("User")
		d.get("fields", {"fieldname": "first_name"})[0].allow_on_submit = 1
		d.get("fields", {"fieldname": "test_custom_field"})[0].allow_on_submit = 1
		d.run_method("save_customization")

		d = self.get_customize_form("User")

		# don't allow for standard fields
		self.assertEquals(d.get("fields", {"fieldname": "first_name"})[0].allow_on_submit or 0, 0)

		# allow for custom field
		self.assertEquals(d.get("fields", {"fieldname": "test_custom_field"})[0].allow_on_submit, 1)

	def test_title_field_pattern(self):
		d = self.get_customize_form("Web Form")

		df = d.get("fields", {"fieldname": "title"})[0]

		# invalid fieldname
		df.default = """{doc_type} - {introduction_test}"""
		self.assertRaises(InvalidFieldNameError, d.run_method, "save_customization")

		# space in formatter
		df.default = """{doc_type} - {introduction text}"""
		self.assertRaises(InvalidFieldNameError, d.run_method, "save_customization")

		# valid fieldname
		df.default = """{doc_type} - {introduction_text}"""
		d.run_method("save_customization")

		# valid fieldname with escaped curlies
		df.default = """{{ {doc_type} }} - {introduction_text}"""
		d.run_method("save_customization")

		# undo
		df.default = None
		d.run_method("save_customization")

