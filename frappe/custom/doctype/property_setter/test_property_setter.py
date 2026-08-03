# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.custom.doctype.property_setter.property_setter import (
	bulk_delete_property_setters,
)
from frappe.tests import IntegrationTestCase


class TestPropertySetter(IntegrationTestCase):
	def test_bulk_delete_property_setters(self):
		doctype = "ToDo"
		fieldname = "status"

		property_1 = "hidden"
		property_2 = "no_copy"
		properties = [property_1, property_2]

		for property_name in properties:
			frappe.make_property_setter(
				{
					"doctype": doctype,
					"fieldname": fieldname,
					"property": property_name,
					"value": 1,
					"property_type": "Check",
				}
			)

		def property_setter_exists(property_name):
			return frappe.db.exists(
				"Property Setter",
				{"doc_type": doctype, "field_name": fieldname, "property": property_name},
			)

		for property_name in properties:
			self.assertTrue(property_setter_exists(property_name))

		# 1
		bulk_delete_property_setters(
			[{"doctype": doctype, "fieldname": fieldname, "property": property_1}],
			bypass_hooks=True,
		)
		self.assertFalse(property_setter_exists(property_1))

		# 2
		bulk_delete_property_setters([{"doc_type": doctype, "field_name": fieldname, "property": property_2}])
		self.assertFalse(property_setter_exists(property_2))
