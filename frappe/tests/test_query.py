import itertools

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.query_builder import Field
from frappe.query_builder.functions import Abs, Count, Ifnull, Max, Now, Timestamp
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.tests.utils import FrappeTestCase
from frappe.utils.nestedset import get_ancestors_of, get_descendants_of


def create_tree_docs():
	records = [
		{
			"some_fieldname": "Root Node",
			"parent_test_tree_doctype": None,
			"is_group": 1,
		},
		{
			"some_fieldname": "Parent 1",
			"parent_test_tree_doctype": "Root Node",
			"is_group": 1,
		},
		{
			"some_fieldname": "Parent 2",
			"parent_test_tree_doctype": "Root Node",
			"is_group": 1,
		},
		{
			"some_fieldname": "Child 1",
			"parent_test_tree_doctype": "Parent 1",
			"is_group": 0,
		},
		{
			"some_fieldname": "Child 2",
			"parent_test_tree_doctype": "Parent 1",
			"is_group": 0,
		},
		{
			"some_fieldname": "Child 3",
			"parent_test_tree_doctype": "Parent 2",
			"is_group": 0,
		},
	]

	tree_doctype = new_doctype("Test Tree DocType", is_tree=True, autoname="field:some_fieldname")
	tree_doctype.insert()

	for record in records:
		d = frappe.new_doc("Test Tree DocType")
		d.update(record)
		d.insert()


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
			"SELECT * FROM `tabDocType` LEFT JOIN `tabBOM Update Log` ON `tabBOM Update Log`.`parent`=`tabDocType`.`name` AND `tabBOM Update Log`.`parenttype`='DocType' WHERE `tabBOM Update Log`.`name` LIKE 'f%' AND `tabDocType`.`parent`='something'",
		)

	@run_only_if(db_type_is.MARIADB)
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
				"User", fields=["`name`, `email`"], filters={"name": "Administrator"}
			).get_sql(),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator")
			.get_sql(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User", fields=["`tabUser`.`name`", "`tabUser`.`email`"], filters={"name": "Administrator"}
			).run(),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator")
			.run(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User",
				fields=["`tabUser`.`name` as owner", "`tabUser`.`email`"],
				filters={"name": "Administrator"},
			).run(as_dict=1),
			frappe.qb.from_("User")
			.select(Field("name").as_("owner"), Field("email"))
			.where(Field("name") == "Administrator")
			.run(as_dict=1),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User", fields=["`tabUser`.`name`, Count(`name`) as count"], filters={"name": "Administrator"}
			).run(),
			frappe.qb.from_("User")
			.select(Field("name"), Count("name").as_("count"))
			.where(Field("name") == "Administrator")
			.run(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User",
				fields=["`tabUser`.`name`, Count(`name`) as `count`"],
				filters={"name": "Administrator"},
			).run(),
			frappe.qb.from_("User")
			.select(Field("name"), Count("name").as_("count"))
			.where(Field("name") == "Administrator")
			.run(),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"User", fields="`tabUser`.`name`, Count(`name`) as `count`", filters={"name": "Administrator"}
			).run(),
			frappe.qb.from_("User")
			.select(Field("name"), Count("name").as_("count"))
			.where(Field("name") == "Administrator")
			.run(),
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

	@run_only_if(db_type_is.MARIADB)
	def test_filters(self):
		self.assertEqual(
			frappe.qb.engine.get_query(
				"User", filters={"IfNull(name, " ")": ("<", Now())}, fields=["Max(name)"]
			).run(),
			frappe.qb.from_("User").select(Max(Field("name"))).where(Ifnull("name", "") < Now()).run(),
		)

	def test_implicit_join_query(self):
		self.assertEqual(
			frappe.qb.engine.get_query(
				"Note",
				filters={"name": "Test Note Title"},
				fields=["name", "`tabNote Seen By`.`user` as seen_by"],
			).get_sql(),
			"SELECT `tabNote`.`name`,`tabNote Seen By`.`user` seen_by FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`name` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`name`='Test Note Title'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"Note",
				filters={"name": "Test Note Title"},
				fields=["name", "`tabNote Seen By`.`user` as seen_by", "`tabNote Seen By`.`idx` as idx"],
			).get_sql(),
			"SELECT `tabNote`.`name`,`tabNote Seen By`.`user` seen_by,`tabNote Seen By`.`idx` idx FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`name` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`name`='Test Note Title'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.engine.get_query(
				"Note",
				filters={"name": "Test Note Title"},
				fields=["name", "seen_by.user as seen_by", "`tabNote Seen By`.`idx` as idx"],
			).get_sql(),
			"SELECT `tabNote`.`name`,`tabNote Seen By`.`user` seen_by,`tabNote Seen By`.`idx` idx FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`name` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`name`='Test Note Title'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

	@run_only_if(db_type_is.MARIADB)
	def test_comment_stripping(self):
		self.assertNotIn(
			"email", frappe.qb.engine.get_query("User", fields=["name", "#email"], filters={}).get_sql()
		)

	def test_nestedset(self):
		frappe.db.sql("delete from `tabDocType` where `name` = 'Test Tree DocType'")
		frappe.db.sql_ddl("drop table if exists `tabTest Tree DocType`")
		create_tree_docs()
		descendants_result = frappe.qb.engine.get_query(
			"Test Tree DocType",
			fields=["name"],
			filters={"name": ("descendants of", "Parent 1")},
			orderby="modified",
		).run(as_list=1)

		# Format decendants result
		descendants_result = list(itertools.chain.from_iterable(descendants_result))
		self.assertListEqual(descendants_result, get_descendants_of("Test Tree DocType", "Parent 1"))

		ancestors_result = frappe.qb.engine.get_query(
			"Test Tree DocType",
			fields=["name"],
			filters={"name": ("ancestors of", "Child 2")},
			orderby="modified",
		).run(as_list=1)

		# Format ancestors result
		ancestors_result = list(itertools.chain.from_iterable(ancestors_result))
		self.assertListEqual(ancestors_result, get_ancestors_of("Test Tree DocType", "Child 2"))

		not_descendants_result = frappe.qb.engine.get_query(
			"Test Tree DocType",
			fields=["name"],
			filters={"name": ("not descendants of", "Parent 1")},
			orderby="modified",
		).run(as_dict=1)

		self.assertListEqual(
			not_descendants_result,
			frappe.db.get_all(
				"Test Tree DocType",
				fields=["name"],
				filters={"name": ("not descendants of", "Parent 1")},
			),
		)

		not_ancestors_result = frappe.qb.engine.get_query(
			"Test Tree DocType",
			fields=["name"],
			filters={"name": ("not ancestors of", "Child 2")},
			orderby="modified",
		).run(as_dict=1)

		self.assertListEqual(
			not_ancestors_result,
			frappe.db.get_all(
				"Test Tree DocType",
				fields=["name"],
				filters={"name": ("not ancestors of", "Child 2")},
			),
		)

		frappe.db.sql("delete from `tabDocType` where `name` = 'Test Tree DocType'")
		frappe.db.sql_ddl("drop table if exists `tabTest Tree DocType`")
