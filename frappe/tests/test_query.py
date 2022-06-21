import unittest

import frappe
from frappe.query_builder import Field
from frappe.tests.test_query_builder import db_type_is, run_only_if


class TestQuery(unittest.TestCase):
	@run_only_if(db_type_is.MARIADB)
	def test_multiple_tables_in_filters(self):
		self.assertEqual(
			frappe.qb.engine.get_sql(
				"DocType",
				["*"],
				[
					["BOM Update Log", "name", "like", "f%"],
					["DocType", "parent", "=", "something"],
				],
			).get_sql(),
			"SELECT * FROM `tabDocType` LEFT JOIN `tabBOM Update Log` ON `tabBOM Update Log`.`parent`=`tabDocType`.`name` WHERE `tabBOM Update Log`.`name` LIKE 'f%' AND `tabDocType`.`parent`='something'",
		)

	def test_string_fields(self):
		self.assertEqual(
			frappe.qb.engine.get_sql("User", fields="name, email", filters={"name": "Administrator"}),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator"),
		)

		self.assertEqual(
			frappe.qb.engine.get_sql("User", fields=["name, email"], filters={"name": "Administrator"}),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator"),
		)

	def test_functions_fields(self):
		from frappe.query_builder.functions import Count

		self.assertEqual(
			frappe.qb.engine.get_sql("User", fields="Count(name)", filters={}),
			frappe.qb.from_("User").select(Count(Field("name"))),
		)

		self.assertEqual(
			frappe.qb.engine.get_sql("User", fields="Count(name), Max(name)", filters={}),
			frappe.qb.from_("User").select(Count(Field("name")), Max(Field("name"))),
		)

		self.assertEqual(
			frappe.qb.engine.get_sql("User", fields=["Count(name)", "Max(name)"], filters={}),
			frappe.qb.from_("User").select(Count(Field("name")), Max(Field("name"))),
		)

		self.assertEqual(
			frappe.qb.engine.get_sql("User", fields=[Count("*")], filters={}),
			frappe.qb.from_("User").select(Count(Field("name")), Max(Field("name"))),
		)

	def test_qb_fields(self):
		user_doctype = frappe.qb.DocType("User")
		self.assertEqual(
			frappe.qb.engine.get_sql(
				user_doctype, fields=[user_doctype.name, user_doctype.email], filters={}
			),
			frappe.qb.from_(user_doctype).select(user_doctype.name, user_doctype.email),
		)

		self.assertEqual(
			frappe.qb.engine.get_sql(user_doctype, fields=user_doctype.email, filters={}),
			frappe.qb.from_(user_doctype).select(user_doctype.email),
		)
