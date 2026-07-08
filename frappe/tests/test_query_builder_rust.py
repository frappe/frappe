import os
import unittest

import frappe
from frappe.query_builder.terms import NamedParameterWrapper


def _enable_rust_qb():
	from frappe.query_builder import rust

	if not rust.is_available():
		raise unittest.SkipTest("frappe-pypika-rs is not installed")

	os.environ[rust.ENV_ENABLE_RUST_QB] = "1"
	rust.patch_querybuilder_get_sql()
	return rust


class TestRustQueryBuilderProxy(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_enable_rust_qb()

	def test_simple_select_matches_pypika_sql(self):
		table = frappe.qb.DocType("Role")

		self.assertEqual(
			frappe.qb.from_(table).select(table.name, table.creation).limit(20).get_sql(),
			"SELECT `name`,`creation` FROM `tabRole` LIMIT 20",
		)

	def test_where_order_limit_sql(self):
		table = frappe.qb.DocType("Role")

		self.assertEqual(
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.name == "Guest")
			.orderby(table.creation, order=frappe.qb.asc)
			.limit(1)
			.get_sql(),
			"SELECT `name` FROM `tabRole` WHERE `name`='Guest' ORDER BY `creation` ASC LIMIT 1",
		)

	def test_parameter_wrapper_is_preserved(self):
		table = frappe.qb.DocType("Role")
		params = NamedParameterWrapper()

		sql = (
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.name == "Administrator' --")
			.get_sql(param_wrapper=params)
		)

		self.assertEqual(sql, "SELECT `name` FROM `tabRole` WHERE `name`=%(param1)s")
		self.assertEqual(params.parameters, {"param1": "Administrator' --"})

	def test_schema_tables_fall_back_to_pypika(self):
		information_schema = frappe.qb.Schema("information_schema")

		self.assertEqual(
			frappe.qb.from_(information_schema.columns)
			.select(information_schema.columns.column_name)
			.where(information_schema.columns.table_name == "tabDocField")
			.get_sql(),
			"SELECT `column_name` FROM `information_schema`.`columns` WHERE `table_name`='tabDocField'",
		)

	def test_join_falls_back_to_pypika(self):
		role = frappe.qb.DocType("Role")
		has_role = frappe.qb.DocType("Has Role")

		self.assertEqual(
			frappe.qb.from_(role).select(role.name).join(has_role).on(role.name == has_role.role).get_sql(),
			"SELECT `tabRole`.`name` FROM `tabRole` JOIN `tabHas Role` ON `tabRole`.`name`=`tabHas Role`.`role`",
		)
