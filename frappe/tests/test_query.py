import unittest

import frappe
from frappe.tests.test_query_builder import db_type_is, run_only_if


@run_only_if(db_type_is.MARIADB)
class TestQuery(unittest.TestCase):
	def test_multiple_tables_in_filters(self):
		self.assertEqual(
			frappe.db.query.get_sql(
				"DocType",
				["*"],
				[
					["BOM Update Log", "name", "like", "f%"],
					["DocType", "parent", "=", "something"],
				],
			).get_sql(),
			"SELECT * FROM `tabDocType` LEFT JOIN `tabBOM Update Log` ON `tabBOM Update Log`.`parent`=`tabDocType`.`name` WHERE `tabBOM Update Log`.`name` LIKE 'f%' AND `tabDocType`.`parent`='something'",
		)
