import frappe
from frappe.query_builder import Field
from frappe.query_builder.functions import Abs, Count, Max, Timestamp
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.tests.utils import FrappeTestCase


class TestQuery(FrappeTestCase):
	@run_only_if(db_type_is.MARIADB)
	def test_multiple_tables_in_filters(self):
		self.assertEqual(
			frappe.qb.engine.get_query(
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
			frappe.qb.engine.get_query(
				"User", fields="name, email", filters={"name": "Administrator"}
			).get_sql(),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator")
			.get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User", fields=["name, email"], filters={"name": "Administrator"}
			).get_sql(),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator")
			.get_sql(),
		)

	def test_functions_fields(self):
		self.assertEqual(
			frappe.qb.engine.get_query("User", fields="Count(name)", filters={}).get_sql(),
			frappe.qb.from_("User").select(Count(Field("name"))).get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query("User", fields=["Count(name)", "Max(name)"], filters={}).get_sql(),
			frappe.qb.from_("User").select(Count(Field("name")), Max(Field("name"))).get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User", fields=["abs(name-email)", "Count(name)"], filters={}
			).get_sql(),
			frappe.qb.from_("User")
			.select(Abs(Field("name") - Field("email")), Count(Field("name")))
			.get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query("User", fields=[Count("*")], filters={}).get_sql(),
			frappe.qb.from_("User").select(Count("*")).get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User", fields="timestamp(creation, modified)", filters={}
			).get_sql(),
			frappe.qb.from_("User").select(Timestamp(Field("creation"), Field("modified"))).get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User", fields="Count(name) as count, Max(email) as max_email", filters={}
			).get_sql(),
			frappe.qb.from_("User")
			.select(Count(Field("name")).as_("count"), Max(Field("email")).as_("max_email"))
			.get_sql(),
		)

	def test_qb_fields(self):
		user_doctype = frappe.qb.DocType("User")
		self.assertEqual(
			frappe.qb.engine.get_query(
				user_doctype, fields=[user_doctype.name, user_doctype.email], filters={}
			).get_sql(),
			frappe.qb.from_(user_doctype).select(user_doctype.name, user_doctype.email).get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(user_doctype, fields=user_doctype.email, filters={}).get_sql(),
			frappe.qb.from_(user_doctype).select(user_doctype.email).get_sql(),
		)

	def test_aliasing(self):
		user_doctype = frappe.qb.DocType("User")
		self.assertEqual(
			frappe.qb.engine.get_query(
				user_doctype, fields=["name as owner", "email as id"], filters={}
			).get_sql(),
			frappe.qb.from_(user_doctype)
			.select(user_doctype.name.as_("owner"), user_doctype.email.as_("id"))
			.get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				user_doctype, fields="name as owner, email as id", filters={}
			).get_sql(),
			frappe.qb.from_(user_doctype)
			.select(user_doctype.name.as_("owner"), user_doctype.email.as_("id"))
			.get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				user_doctype, fields=["Count(name) as count", "email as id"], filters={}
			).get_sql(),
			frappe.qb.from_(user_doctype)
			.select(user_doctype.email.as_("id"), Count(Field("name")).as_("count"))
			.get_sql(),
		)
