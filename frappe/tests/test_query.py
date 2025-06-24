import itertools

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.permissions import add_permission, update_permission_property
from frappe.query_builder import Field
from frappe.query_builder.functions import Abs, Count, Ifnull, Max, Now, Timestamp
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import enable_safe_exec
from frappe.tests.test_db_query import (
	create_nested_doctype,
	create_nested_doctype_records,
	setup_patched_blog_post,
	setup_test_user,
)
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.utils.nestedset import get_ancestors_of, get_descendants_of

EXTRA_TEST_RECORD_DEPENDENCIES = ["User", "Blog Post", "Blog Category", "Blogger"]


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


class TestQuery(IntegrationTestCase):
	@run_only_if(db_type_is.MARIADB)
	def test_multiple_tables_in_filters(self):
		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				["*"],
				[
					["DocField", "name", "like", "f%"],
					["DocType", "parent", "=", "something"],
				],
			).get_sql(),
			"SELECT `tabDocType`.* FROM `tabDocType` LEFT JOIN `tabDocField` ON `tabDocField`.`parent`=`tabDocType`.`name` AND `tabDocField`.`parenttype`='DocType' AND `tabDocField`.`parentfield`='fields' WHERE `tabDocField`.`name` LIKE 'f%' AND `tabDocType`.`parent`='something'",
		)

	@run_only_if(db_type_is.MARIADB)
	def test_string_fields(self):
		self.assertEqual(
			frappe.qb.get_query("User", fields="name, email", filters={"name": "Administrator"}).get_sql(),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator")
			.get_sql(),
		)
		self.assertEqual(
			frappe.qb.get_query(
				"User", fields=["`name`, `email`"], filters={"name": "Administrator"}
			).get_sql(),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator")
			.get_sql(),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"User", fields=["`tabUser`.`name`", "`tabUser`.`email`"], filters={"name": "Administrator"}
			).run(),
			frappe.qb.from_("User")
			.select(Field("name"), Field("email"))
			.where(Field("name") == "Administrator")
			.run(),
		)

		self.assertEqual(
			frappe.qb.get_query(
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
			frappe.qb.get_query("User", fields=[Count("*")]).get_sql(),
			frappe.qb.from_("User").select(Count("*")).get_sql(),
		)

	def test_qb_fields(self):
		user_doctype = frappe.qb.DocType("User")
		self.assertEqual(
			frappe.qb.get_query(
				user_doctype, fields=[user_doctype.name, user_doctype.email], filters={}
			).get_sql(),
			frappe.qb.from_(user_doctype).select(user_doctype.name, user_doctype.email).get_sql(),
		)

		self.assertEqual(
			frappe.qb.get_query(user_doctype, fields=user_doctype.email, filters={}).get_sql(),
			frappe.qb.from_(user_doctype).select(user_doctype.email).get_sql(),
		)

	def test_field_validation_select(self):
		"""Test validation for fields in SELECT clause."""

		valid_fields = [
			"name",
			"`name`",
			"tabUser.name",
			"`tabUser`.`name`",
			"name as alias",
			"`name` as alias",
			"tabUser.name as alias",
			"`tabUser`.`name` as alias",
			"*",
			"`tabHas Role`.`name`",
		]
		invalid_fields = [
			"name; DROP TABLE users",
			"`name` ; SELECT * FROM secrets",
			"name--comment",
			"name /* comment */",
			"name AS alias; --",
			"invalid-field-name",
			"table.invalid-field",
			"`table`.`invalid-field`",
			"field with space",
			"`field with space`",
			"field as alias with space",
			"field as `alias with space`",
			"COUNT(*)",
			"COUNT(name)",
			"SUM(amount) as total",
			"COUNT(name) as alias; SELECT 1",
			"COUNT(name;)",
			"`name",
			"name`",
			"`tabUser.name`",
			"tabUser.`name",
			"tabUser`.`name`",
			"tab`User.name",
		]

		for field in valid_fields:
			try:
				frappe.qb.get_query("User", fields=field).get_sql()
				# Test as list item too
				frappe.qb.get_query("User", fields=[field]).get_sql()
			except Exception as e:
				self.fail(f"Valid SELECT field '{field}' failed validation: {e}")

		for field in invalid_fields:
			with self.assertRaises(
				(frappe.PermissionError, frappe.ValidationError),
				msg=f"Invalid SELECT field '[{field}]' passed validation",
			):
				frappe.qb.get_query("User", fields=[field]).get_sql()

	def test_field_validation_filters(self):
		"""Test validation for fields used in filters (WHERE clause)."""
		valid_fields = ["name", "creation", "language.name"]
		# Filters should not allow aliases or functions directly as field names
		invalid_fields = [
			"tabUser.name",
			"`tabUser`.`name`",
			"name as alias",
			"`name` as alias",
			"tabUser.name as alias",
			"`tabUser`.`name` as alias",
			"COUNT(*)",
			"COUNT(name)",
			"name; DROP TABLE users",
			"`name` ; SELECT * FROM secrets",
			"name--comment",
			"name /* comment */",
			"invalid-field-name",
			"table.invalid-field",
			"`table`.`invalid-field`",
			"field with space",
			"`field with space`",
			"`name`",
			"`name",
			"name`",
			"tabUser.`name`",
			"`tabUser.name`",
		]

		for field in valid_fields:
			try:
				# Test in dict filter
				frappe.qb.get_query("User", filters={field: "value"}).get_sql()
				# Test in list filter
				frappe.qb.get_query("User", filters=[[field, "=", "value"]]).get_sql()
				# Test in list filter with doctype
				frappe.qb.get_query("User", filters=[["User", field, "=", "value"]]).get_sql()
			except Exception as e:
				self.fail(f"Valid filter field '{field}' failed validation: {e}")

		for field in invalid_fields:
			with self.assertRaises(
				frappe.ValidationError, msg=f"Invalid filter field '{{{field}: val}}' passed validation"
			):
				frappe.qb.get_query("User", filters={field: "value"}).get_sql()

	def test_field_validation_group_by(self):
		"""Test validation for fields in GROUP BY clause."""
		valid_fields = [
			"name",
			"1",  # Allow numeric indices
			"name, email",
			"1, 2",
		]
		# GROUP BY should not allow aliases or functions
		invalid_fields = [
			"name as alias",
			"COUNT(*)",
			"COUNT(name)",
			"name; DROP TABLE users",
			"`name` ; SELECT * FROM secrets",
			"name--comment",
			"name /* comment */",
			"invalid-field-name",
			"table.invalid-field",
			"tabUser.name",
			"`name`",
			"`tabUser`.`name`",
			"`name`, `tabUser`.`email`",
			"`table`.`invalid-field`",
			"field with space",
			"`field with space`",
			"name, email; SELECT 1",
		]

		for group_by_str in valid_fields:
			try:
				frappe.qb.get_query("User", group_by=group_by_str).get_sql()
			except Exception as e:
				self.fail(f"Valid GROUP BY string '{group_by_str}' failed validation: {e}")

		for group_by_str in invalid_fields:
			with self.assertRaises(
				(frappe.PermissionError, frappe.ValidationError),
				msg=f"Invalid GROUP BY string '{group_by_str}' passed validation",
			):
				frappe.qb.get_query("User", group_by=group_by_str).get_sql()

	def test_field_validation_order_by(self):
		"""Test validation for fields in ORDER BY clause."""
		valid_fields = [
			"name",
			"1",  # Allow numeric indices
			"name asc",
			"1 asc",
			"2 DESC",
			"name, email",
			"1 asc, 2 desc",
		]
		# ORDER BY should not allow aliases or functions, or invalid directions
		invalid_fields = [
			"name as alias",
			"COUNT(*)",
			"COUNT(name)",
			"name; DROP TABLE users",
			"`name` ; SELECT * FROM secrets",
			"name--comment",
			"name /* comment */",
			"`name`",
			"tabUser.name",
			"`tabUser`.`name`",
			"`name` DESC",
			"tabUser.name Asc",
			"`tabUser`.`name` desc",
			"`name` asc, `tabUser`.`email` DESC",
			"invalid-field-name",
			"table.invalid-field",
			"`table`.`invalid-field`",
			"field with space",
			"`field with space`",
			"name sideways",
			"name ASC;",
			"name, email; SELECT 1",
			"name INVALID_DIRECTION",
		]

		for order_by_str in valid_fields:
			try:
				frappe.qb.get_query("User", order_by=order_by_str).get_sql()
			except Exception as e:
				self.fail(f"Valid ORDER BY string '{order_by_str}' failed validation: {e}")

		for order_by_str in invalid_fields:
			with self.assertRaises(
				(frappe.PermissionError, ValueError, frappe.ValidationError),
				msg=f"Invalid ORDER BY string '{order_by_str}' passed validation",
			):
				frappe.qb.get_query("User", order_by=order_by_str).get_sql()

	def test_aliasing(self):
		user_doctype = frappe.qb.DocType("User")
		self.assertEqual(
			frappe.qb.get_query("User", fields=["name as owner", "email as id"], filters={}).get_sql(),
			frappe.qb.from_(user_doctype)
			.select(user_doctype.name.as_("owner"), user_doctype.email.as_("id"))
			.get_sql(),
		)

		self.assertEqual(
			frappe.qb.get_query(user_doctype, fields="name as owner, email as id", filters={}).get_sql(),
			frappe.qb.from_(user_doctype)
			.select(user_doctype.name.as_("owner"), user_doctype.email.as_("id"))
			.get_sql(),
		)

	@run_only_if(db_type_is.MARIADB)
	def test_filters(self):
		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				fields=["name"],
				filters={"module.app_name": "frappe"},
			).get_sql(),
			"SELECT `tabDocType`.`name` FROM `tabDocType` LEFT JOIN `tabModule Def` ON `tabModule Def`.`name`=`tabDocType`.`module` WHERE `tabModule Def`.`app_name`='frappe'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				fields=["name"],
				filters={"module.app_name": ("like", "frap%")},
			).get_sql(),
			"SELECT `tabDocType`.`name` FROM `tabDocType` LEFT JOIN `tabModule Def` ON `tabModule Def`.`name`=`tabDocType`.`module` WHERE `tabModule Def`.`app_name` LIKE 'frap%'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				fields=["name"],
				filters={"permissions.role": "System Manager"},
			).get_sql(),
			"SELECT `tabDocType`.`name` FROM `tabDocType` LEFT JOIN `tabDocPerm` ON `tabDocPerm`.`parent`=`tabDocType`.`name` AND `tabDocPerm`.`parenttype`='DocType' AND `tabDocPerm`.`parentfield`='permissions' WHERE `tabDocPerm`.`role`='System Manager'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				fields=["module"],
				filters="",
			).get_sql(),
			"SELECT `module` FROM `tabDocType` WHERE `name`=''".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				filters=["ToDo", "Note"],
			).get_sql(),
			"SELECT `name` FROM `tabDocType` WHERE `name` IN ('ToDo','Note')".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				filters={"name": ("in", [])},
			).get_sql(),
			"SELECT `name` FROM `tabDocType` WHERE `name` IN ('')".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				filters=[1, 2, 3],
			).get_sql(),
			"SELECT `name` FROM `tabDocType` WHERE `name` IN (1,2,3)".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				filters=[],
			).get_sql(),
			"SELECT `name` FROM `tabDocType`".replace("`", '"' if frappe.db.db_type == "postgres" else "`"),
		)

	def test_nested_filters(self):
		"""Test nested filter conditions with AND/OR logic."""
		User = frappe.qb.DocType("User")

		# Simple AND
		filters_and = [
			["email", "=", "admin@example.com"],
			"and",
			["first_name", "=", "Admin"],
		]
		expected_sql_and = (
			frappe.qb.from_(User)
			.select(User.name)
			.where((User.email == "admin@example.com") & (User.first_name == "Admin"))
			.get_sql()
		)
		self.assertEqual(frappe.qb.get_query("User", filters=filters_and).get_sql(), expected_sql_and)

		# Simple OR
		filters_or = [
			["email", "=", "admin@example.com"],
			"or",
			["email", "=", "guest@example.com"],
		]
		expected_sql_or = (
			frappe.qb.from_(User)
			.select(User.name)
			.where((User.email == "admin@example.com") | (User.email == "guest@example.com"))
			.get_sql()
		)
		self.assertEqual(frappe.qb.get_query("User", filters=filters_or).get_sql(), expected_sql_or)

		# Mixed AND/OR
		filters_mixed = [
			["first_name", "=", "Admin"],
			"and",
			[["email", "=", "admin@example.com"], "or", ["email", "=", "guest@example.com"]],
		]
		expected_sql_mixed = (
			frappe.qb.from_(User)
			.select(User.name)
			.where(
				(User.first_name == "Admin")
				& ((User.email == "admin@example.com") | (User.email == "guest@example.com"))
			)
			.get_sql()
		)
		self.assertEqual(frappe.qb.get_query("User", filters=filters_mixed).get_sql(), expected_sql_mixed)

		# Nested AND/OR
		filters_nested = [
			[["first_name", "=", "Admin"], "and", ["enabled", "=", 1]],
			"or",
			[["first_name", "=", "Guest"], "and", ["enabled", "=", 0]],
		]
		expected_sql_nested = (
			frappe.qb.from_(User)
			.select(User.name)
			.where(
				((User.first_name == "Admin") & (User.enabled == 1))
				| ((User.first_name == "Guest") & (User.enabled == 0))
			)
			.get_sql()
		)
		self.assertEqual(frappe.qb.get_query("User", filters=filters_nested).get_sql(), expected_sql_nested)

		# Single Grouped Condition (wrapped in extra list)
		filters_single_group = [[["first_name", "=", "Admin"], "and", ["enabled", "=", 1]]]
		expected_sql_single_group = (
			frappe.qb.from_(User)
			.select(User.name)
			.where((User.first_name == "Admin") & (User.enabled == 1))
			.get_sql()
		)
		self.assertEqual(
			frappe.qb.get_query("User", filters=filters_single_group).get_sql(), expected_sql_single_group
		)

		# Test with different operators and values
		filters_complex = [
			["creation", ">", "2023-01-01"],
			"and",
			[
				["email", "like", "%@example.com"],
				"or",
				[["first_name", "in", ["Admin", "Guest"]], "and", ["enabled", "!=", 1]],
			],
		]
		expected_sql_complex = (
			frappe.qb.from_(User)
			.select(User.name)
			.where(
				(User.creation > "2023-01-01")
				& (
					(User.email.like("%@example.com"))
					| ((User.first_name.isin(["Admin", "Guest"])) & (User.enabled != 1))
				)
			)
			.get_sql()
		)
		self.assertEqual(frappe.qb.get_query("User", filters=filters_complex).get_sql(), expected_sql_complex)

	def test_invalid_nested_filters(self):
		"""Test invalid formats for nested filters."""
		# Invalid operator
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", filters=[["email", "=", "a"], "xor", ["email", "=", "b"]]).get_sql()
		self.assertIn("Expected 'and' or 'or' operator", str(cm.exception))

		# Missing condition after operator
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", filters=[["email", "=", "a"], "and"]).get_sql()
		self.assertIn("Filter condition missing after operator", str(cm.exception))

		# Starting with operator
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", filters=["and", ["email", "=", "a"]]).get_sql()
		self.assertIn("Invalid start for filter condition", str(cm.exception))

		# Invalid condition type (string instead of list/tuple)
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", filters=[["email", "=", "a"], "and", "enabled = 1"]).get_sql()
		self.assertIn("Invalid filter condition", str(cm.exception))

		# Malformed simple filter inside nested
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query(
				"User", filters=[["email", "=", "a", "extra"], "and", ["enabled", "=", 1]]
			).get_sql()
		self.assertIn("Invalid simple filter format", str(cm.exception))

		# Nested list doesn't start with a condition list/tuple
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", filters=["email", "and", ["enabled", "=", 1]]).get_sql()
		self.assertIn("Invalid start for filter condition", str(cm.exception))

	def test_implicit_join_query(self):
		self.maxDiff = None

		self.assertEqual(
			frappe.qb.get_query(
				"Note",
				filters={"name": "Test Note Title"},
				fields=["name", "`tabNote Seen By`.`user` as seen_by"],
			).get_sql(),
			"SELECT `tabNote`.`name`,`tabNote Seen By`.`user` `seen_by` FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`name` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`name`='Test Note Title'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		# output doesn't contain parentfield condition because it can't be inferred
		self.assertEqual(
			frappe.qb.get_query(
				"Note",
				filters={"name": "Test Note Title"},
				fields=["name", "`tabNote Seen By`.`user` as seen_by", "`tabNote Seen By`.`idx` as idx"],
			).get_sql(),
			"SELECT `tabNote`.`name`,`tabNote Seen By`.`user` `seen_by`,`tabNote Seen By`.`idx` `idx` FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`name` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`name`='Test Note Title'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		# output contains parentfield condition because it can be inferred by "seen_by.user"
		self.assertEqual(
			frappe.qb.get_query(
				"Note",
				filters={"name": "Test Note Title"},
				fields=["name", "seen_by.user as seen_by", "`tabNote Seen By`.`idx` as idx"],
			).get_sql(),
			"SELECT `tabNote`.`name`,`tabNote Seen By`.`user` `seen_by`,`tabNote Seen By`.`idx` `idx` FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`name` AND `tabNote Seen By`.`parenttype`='Note' AND `tabNote Seen By`.`parentfield`='seen_by' WHERE `tabNote`.`name`='Test Note Title'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"DocType",
				fields=["name", "module.app_name as app_name"],
			).get_sql(),
			"SELECT `tabDocType`.`name`,`tabModule Def`.`app_name` `app_name` FROM `tabDocType` LEFT JOIN `tabModule Def` ON `tabModule Def`.`name`=`tabDocType`.`module`".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

	# fields now has strict validation, so this test is not valid anymore
	# @run_only_if(db_type_is.MARIADB)
	# def test_comment_stripping(self):
	# 	self.assertNotIn(
	# 		"email", frappe.qb.get_query("User", fields=["name", "#email"], filters={}).get_sql()
	# 	)

	def test_nestedset(self):
		frappe.db.sql("delete from `tabDocType` where `name` = 'Test Tree DocType'")
		frappe.db.sql_ddl("drop table if exists `tabTest Tree DocType`")
		create_tree_docs()
		descendants_result = frappe.qb.get_query(
			"Test Tree DocType",
			fields=["name"],
			filters={"name": ("descendants of", "Parent 1")},
			order_by="creation desc",
		).run(as_list=1)

		# Format decendants result
		descendants_result = list(itertools.chain.from_iterable(descendants_result))
		self.assertListEqual(descendants_result, get_descendants_of("Test Tree DocType", "Parent 1"))

		ancestors_result = frappe.qb.get_query(
			"Test Tree DocType",
			fields=["name"],
			filters={"name": ("ancestors of", "Child 2")},
			order_by="creation desc",
		).run(as_list=1)

		# Format ancestors result
		ancestors_result = list(itertools.chain.from_iterable(ancestors_result))
		self.assertListEqual(ancestors_result, get_ancestors_of("Test Tree DocType", "Child 2"))

		not_descendants_result = frappe.qb.get_query(
			"Test Tree DocType",
			fields=["name"],
			filters={"name": ("not descendants of", "Parent 1")},
			order_by="creation desc",
		).run(as_dict=1)

		self.assertListEqual(
			not_descendants_result,
			frappe.db.get_all(
				"Test Tree DocType",
				fields=["name"],
				filters={"name": ("not descendants of", "Parent 1")},
			),
		)

		not_ancestors_result = frappe.qb.get_query(
			"Test Tree DocType",
			fields=["name"],
			filters={"name": ("not ancestors of", "Child 2")},
			order_by="creation desc",
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

	def test_child_field_syntax(self):
		note1 = frappe.get_doc(doctype="Note", title="Note 1", seen_by=[{"user": "Administrator"}]).insert()
		note2 = frappe.get_doc(
			doctype="Note", title="Note 2", seen_by=[{"user": "Administrator"}, {"user": "Guest"}]
		).insert()

		result = frappe.qb.get_query(
			"Note",
			filters={"name": ["in", [note1.name, note2.name]]},
			fields=["name", {"seen_by": ["*"]}],
			order_by="title asc",
		).run(as_dict=1)

		self.assertTrue(isinstance(result[0].seen_by, list))
		self.assertTrue(isinstance(result[1].seen_by, list))
		self.assertEqual(len(result[0].seen_by), 1)
		self.assertEqual(len(result[1].seen_by), 2)
		self.assertEqual(result[0].seen_by[0].user, "Administrator")

		result = frappe.qb.get_query(
			"Note",
			filters={"name": ["in", [note1.name, note2.name]]},
			fields=["name", {"seen_by": ["user"]}],
			order_by="title asc",
		).run(as_dict=1)

		self.assertEqual(len(result[0].seen_by[0].keys()), 1)
		self.assertEqual(result[1].seen_by[1].user, "Guest")

		note1.delete()
		note2.delete()

	def test_build_match_conditions(self):
		from frappe.permissions import add_user_permission, clear_user_permissions_for_doctype

		clear_user_permissions_for_doctype("Blog Post", "test2@example.com")

		test2user = frappe.get_doc("User", "test2@example.com")
		test2user.add_roles("Blogger")
		frappe.set_user("test2@example.com")

		# Before any user permission is applied, there should be no conditions
		query = frappe.qb.get_query("Blog Post", ignore_permissions=False)
		self.assertNotIn("(`tabBlog Post`.`name` in (", str(query))

		# Add user permissions
		add_user_permission("Blog Post", "-test-blog-post", "test2@example.com", True)
		add_user_permission("Blog Post", "-test-blog-post-1", "test2@example.com", True)

		# After applying user permission, condition should be in query
		query = str(frappe.qb.get_query("Blog Post", ignore_permissions=False))

		# Check for user permission condition in the query string
		if frappe.db.db_type == "mariadb":
			self.assertIn("`name` IS NULL OR `name` IN ('-test-blog-post-1','-test-blog-post')", query)
		elif frappe.db.db_type == "postgres":
			self.assertIn("\"name\" IS NULL OR \"name\" IN ('-test-blog-post-1','-test-blog-post')", query)

		frappe.set_user("Administrator")
		clear_user_permissions_for_doctype("Blog Post", "test2@example.com")
		test2user.remove_roles("Blogger")

	def test_ignore_permissions_for_query(self):
		frappe.set_user("test2@example.com")

		with self.assertRaises(frappe.PermissionError):
			frappe.qb.get_query("DocType", filters={"istable": 1}, ignore_permissions=False)

		result = frappe.qb.get_query("DocType", filters={"istable": 1}, ignore_permissions=True).run()
		self.assertTrue(len(result) > 0)

		frappe.set_user("Administrator")

	def test_permlevel_fields(self):
		"""Test permission level check when querying fields"""
		with setup_patched_blog_post(), setup_test_user(set_user=True):
			# Create a test blog post
			test_post = frappe.get_doc(
				{
					"doctype": "Blog Post",
					"title": "Test Permission Post",
					"content": "Test Content",
					"blog_category": "-test-blog-category",
					"published": 1,
				}
			).insert(ignore_permissions=True, ignore_mandatory=True)

			# Without proper permission, published field should be filtered out
			data = frappe.qb.get_query(
				"Blog Post",
				filters={"name": test_post.name},
				fields=["name", "published", "title"],
				ignore_permissions=False,
			).run(as_dict=1)

			field_list = [field for d in data for field in d.keys()]
			self.assertIn("title", field_list)
			self.assertIn("name", field_list)
			self.assertNotIn("published", field_list)

			# With Administrator, all fields should be accessible
			frappe.set_user("Administrator")
			data = frappe.qb.get_query(
				"Blog Post",
				filters={"name": test_post.name},
				fields=["name", "published", "title"],
				ignore_permissions=False,
			).run(as_dict=1)

			field_list = [field for d in data for field in d.keys()]
			self.assertIn("published", field_list)

			test_post.delete()

	def test_child_table_access_with_select_permission(self):
		"""Test that child table fields are inaccessible if user only has select perm on parent."""

		test_role = "Select Note Test Role"
		test_user_email = "test2@example.com"  # Use existing test user
		test_note_title = "Child Select Test Note"

		# Cleanup
		frappe.set_user("Administrator")
		test_user = frappe.get_doc("User", test_user_email)
		test_user.remove_roles(test_role)
		frappe.delete_doc("Role", test_role, ignore_missing=True, force=True)
		frappe.delete_doc("Note", {"title": test_note_title}, ignore_missing=True, force=True)

		# Setup Role with 'select' on Note and 'read' on Note Seen By
		frappe.get_doc({"doctype": "Role", "role_name": test_role}).insert(ignore_if_duplicate=True)
		# Grant select on Note, read on Note Seen By
		add_permission("Note", test_role, 0, ptype="select")
		add_permission("Note Seen By", test_role, 0, ptype="read")
		# Ensure no read permission on Note for this role by explicitly setting it to 0
		update_permission_property("Note", test_role, 0, "read", 0, validate=False)
		test_user.add_roles(test_role)

		note = frappe.get_doc(
			doctype="Note", title=test_note_title, public=1, seen_by=[{"user": "Administrator"}]
		).insert(ignore_permissions=True)

		frappe.set_user(test_user_email)
		query = frappe.qb.get_query(
			"Note",
			filters={"name": note.name},
			fields=["name", {"seen_by": ["user"]}],
			ignore_permissions=False,
		)
		result = query.run(as_dict=True)

		self.assertEqual(len(result), 1, "Should find the note record")
		self.assertIn("name", result[0], "Parent field 'name' should be accessible")
		self.assertNotIn(
			"seen_by",
			result[0],
			"Child table field 'seen_by' should NOT be accessible with only 'select' on parent",
		)

		# Cleanup
		frappe.set_user("Administrator")
		note.delete(ignore_permissions=True)
		test_user.remove_roles(test_role)
		frappe.delete_doc("Role", test_role, force=True)

	def test_nested_permission(self):
		"""Test permission on nested doctypes"""
		frappe.set_user("Administrator")
		create_nested_doctype()
		create_nested_doctype_records()

		from frappe.permissions import add_user_permission, clear_user_permissions_for_doctype

		clear_user_permissions_for_doctype("Nested DocType")

		# Add user permission for only one root folder
		add_user_permission("Nested DocType", "Level 1 A", "test2@example.com")

		from frappe.core.page.permission_manager.permission_manager import update

		# To avoid if_owner filter
		update("Nested DocType", "All", 0, "if_owner", 0)

		test2user = frappe.get_doc("User", "test2@example.com")
		test2user.add_roles("Blogger")
		frappe.set_user("test2@example.com")
		data = frappe.qb.get_query("Nested DocType", ignore_permissions=False).run(as_dict=1)

		# Children of the permitted node should be accessible
		self.assertTrue(any(d.name == "Level 2 A" for d in data))

		# Other nodes should not be accessible
		self.assertFalse(any(d.name == "Level 1 B" for d in data))
		self.assertFalse(any(d.name == "Level 2 B" for d in data))

		update("Nested DocType", "All", 0, "if_owner", 1)  # Reset to default
		frappe.set_user("Administrator")

	def test_is_set_is_not_set(self):
		"""Test is set and is not set filters"""
		result = frappe.qb.get_query("DocType", filters={"autoname": ["is", "not set"]}).run(as_dict=1)
		self.assertTrue({"name": "Integration Request"} in result)
		self.assertTrue({"name": "User"} in result)
		self.assertFalse({"name": "Blogger"} in result)

		result = frappe.qb.get_query("DocType", filters={"autoname": ["is", "set"]}).run(as_dict=1)
		self.assertTrue({"name": "DocField"} in result)
		self.assertTrue({"name": "Prepared Report"} in result)
		self.assertFalse({"name": "Property Setter"} in result)

		# Test with updating value to NULL
		frappe.db.set_value("DocType", "Property Setter", "autoname", None, update_modified=False)

		result = frappe.qb.get_query("DocType", filters={"autoname": ["is", "set"]}).run(as_dict=1)
		self.assertFalse(any(d.name == "Property Setter" for d in result))

	def test_permission_query_condition(self):
		"""Test permission query condition being applied from hooks and server script"""
		from frappe.desk.doctype.dashboard_settings.dashboard_settings import create_dashboard_settings

		# Create a Dashboard Settings for test user
		self.doctype = "Dashboard Settings"
		self.user = "test@example.com"

		original_hooks = frappe.get_hooks("permission_query_conditions") or {}

		# Create test data
		create_dashboard_settings(self.user)

		# Hook condition will restrict to only name=Administrator, so our test user's record should not be found
		query = frappe.qb.get_query("Dashboard Settings", user=self.user, ignore_permissions=False)
		self.assertIn("`tabDashboard Settings`.name = ", str(query))

		# Create a server script for permission query
		script = frappe.new_doc(
			doctype="Server Script",
			name="Dashboard Settings Permission Query",
			script_type="Permission Query",
			enabled=1,
			reference_doctype="Dashboard Settings",
			script=f"""conditions = '`tabDashboard Settings`.`user` = "{self.user}"'""",
		).insert()

		# Test with server script
		# Script condition should allow the record to be found
		frappe.clear_cache()
		frappe.hooks.permission_query_conditions = {}  # Clear hooks to test server script alone

		with enable_safe_exec():
			query = frappe.qb.get_query("Dashboard Settings", user=self.user, ignore_permissions=False)
			self.assertIn(f'`tabDashboard Settings`.`user` = "{self.user}"', str(query))

		# Cleanup
		script.delete()
		frappe.clear_cache()
		frappe.hooks.permission_query_conditions = original_hooks

	def test_link_field_target_permission(self):
		"""Test that accessing link_field.target_field respects target field's permlevel."""
		target_dt_name = "TargetDocForLinkPerm"
		source_dt_name = "SourceDocForLinkPerm"
		test_role = "LinkPermTestRole"
		test_user = "test2@example.com"

		# Cleanup previous runs
		frappe.set_user("Administrator")
		frappe.delete_doc("DocType", target_dt_name, ignore_missing=True, force=True)
		frappe.delete_doc("DocType", source_dt_name, ignore_missing=True, force=True)
		frappe.delete_doc("Role", test_role, ignore_missing=True, force=True)
		test_user_doc = frappe.get_doc("User", test_user)
		test_user_doc.remove_roles(test_role)

		# Create Doctypes
		target_dt = new_doctype(
			target_dt_name,
			fields=[
				{"fieldname": "target_field", "fieldtype": "Data", "permlevel": 1, "label": "Target Field"},
				{"fieldname": "other_target_field", "fieldtype": "Data", "label": "Other Target Field"},
			],
		).insert(ignore_if_duplicate=True)

		source_dt = new_doctype(
			source_dt_name,
			fields=[
				{
					"fieldname": "link_field",
					"fieldtype": "Link",
					"options": target_dt_name,
					"label": "Link Field",
				}
			],
		).insert(ignore_if_duplicate=True)

		# Create Records
		target_doc = frappe.get_doc(
			doctype=target_dt_name, target_field="Secret Data", other_target_field="Public Data"
		).insert(ignore_permissions=True)
		source_doc = frappe.get_doc(doctype=source_dt_name, link_field=target_doc.name).insert(
			ignore_permissions=True
		)

		# Setup Role and Permissions
		frappe.get_doc({"doctype": "Role", "role_name": test_role}).insert(ignore_if_duplicate=True)
		add_permission(source_dt_name, test_role, 0, ptype="read")
		add_permission(target_dt_name, test_role, 0, ptype="read")
		# Ensure no permlevel 1 read for test_role
		update_permission_property(target_dt_name, test_role, 1, "read", 0, validate=False)
		# Ensure System Manager can read permlevel 1
		add_permission(target_dt_name, "System Manager", 1, ptype="read")
		test_user_doc.add_roles(test_role)

		# Test as the restricted user
		frappe.set_user(test_user)
		result_restricted = frappe.qb.get_query(
			source_dt_name,
			filters={"name": source_doc.name},
			fields=[
				"name",
				"link_field.target_field as linked_secret",
				"link_field.other_target_field as linked_public",
			],
			ignore_permissions=False,
		).run(as_dict=True)

		self.assertEqual(len(result_restricted), 1)
		self.assertIn(
			"linked_public",
			result_restricted[0],
			"Permlevel 0 target field should be accessible via link.",
		)
		self.assertNotIn(
			"linked_secret",
			result_restricted[0],
			"Permlevel 1 target field should NOT be accessible via link for restricted user.",
		)

		# Test as Administrator (who has System Manager role)
		frappe.set_user("Administrator")
		result_admin = frappe.qb.get_query(
			source_dt_name,
			filters={"name": source_doc.name},
			fields=[
				"name",
				"link_field.target_field as linked_secret",
				"link_field.other_target_field as linked_public",
			],
			ignore_permissions=False,  # Still check permissions, but Admin has them
		).run(as_dict=True)

		self.assertEqual(len(result_admin), 1)
		self.assertIn(
			"linked_public", result_admin[0], "Permlevel 0 target field should be accessible for Admin."
		)
		self.assertIn(
			"linked_secret", result_admin[0], "Permlevel 1 target field should be accessible for Admin."
		)
		self.assertEqual(result_admin[0].linked_secret, "Secret Data")

		# Cleanup
		frappe.set_user("Administrator")
		source_doc.delete(ignore_permissions=True)
		target_doc.delete(ignore_permissions=True)
		source_dt.delete()
		target_dt.delete()
		test_user_doc.remove_roles(test_role)
		frappe.delete_doc("Role", test_role, force=True)

	def test_filter_direct_field_permission(self):
		"""Test that filtering is only allowed on permitted direct fields."""
		with setup_patched_blog_post(), setup_test_user(set_user=True) as user:
			# Create a test blog post
			test_post = frappe.get_doc(
				{
					"doctype": "Blog Post",
					"title": "Test Filter Permission Post",
					"content": "Test Content",
					"blog_category": "-test-blog-category",
					"published": 1,  # permlevel 1
				}
			).insert(ignore_permissions=True, ignore_mandatory=True, ignore_if_duplicate=True)

			# User has read permlevel 0, but not 1 (published field)
			# Try filtering on permitted field (title - permlevel 0)
			try:
				frappe.qb.get_query(
					"Blog Post",
					filters={"title": test_post.title},
					ignore_permissions=False,
					user=user.name,
				).run()
			except frappe.PermissionError as e:
				self.fail(f"Filtering on permitted field 'title' failed: {e}")

			# Try filtering on non-permitted field (published - permlevel 1)
			with self.assertRaises(frappe.PermissionError) as cm:
				frappe.qb.get_query(
					"Blog Post",
					filters={"published": 1},
					ignore_permissions=False,
					user=user.name,
				).run()
			self.assertIn("You do not have permission to access field", str(cm.exception))
			self.assertIn("Blog Post.published", str(cm.exception))

			# Cleanup
			frappe.set_user("Administrator")
			test_post.delete()

	def test_filter_linked_field_permission(self):
		"""Test that filtering is only allowed on permitted linked fields."""
		with setup_test_user(set_user=True) as user:
			target_dt_name = "TargetDocForFilterPerm"
			source_dt_name = "SourceDocForFilterPerm"
			test_role = "FilterPermTestRole"

			# Cleanup previous runs
			frappe.set_user("Administrator")
			frappe.delete_doc("DocType", target_dt_name, ignore_missing=True, force=True)
			frappe.delete_doc("DocType", source_dt_name, ignore_missing=True, force=True)
			frappe.delete_doc("Role", test_role, ignore_missing=True, force=True)
			test_user_doc = frappe.get_doc("User", user.name)
			test_user_doc.remove_roles(test_role)

			# Create Doctypes
			target_dt = new_doctype(
				target_dt_name,
				fields=[
					{
						"fieldname": "target_field",
						"fieldtype": "Data",
						"permlevel": 1,
						"label": "Target Field",
					},
					{"fieldname": "other_target_field", "fieldtype": "Data", "label": "Other Target Field"},
				],
			).insert(ignore_if_duplicate=True)

			source_dt = new_doctype(
				source_dt_name,
				fields=[
					{
						"fieldname": "link_field",
						"fieldtype": "Link",
						"options": target_dt_name,
						"label": "Link Field",
					}
				],
			).insert(ignore_if_duplicate=True)

			# Create Records
			target_doc = frappe.get_doc(
				doctype=target_dt_name, target_field="Secret Data", other_target_field="Public Data"
			).insert(ignore_permissions=True)
			source_doc = frappe.get_doc(doctype=source_dt_name, link_field=target_doc.name).insert(
				ignore_permissions=True
			)

			# Setup Role and Permissions
			frappe.get_doc({"doctype": "Role", "role_name": test_role}).insert(ignore_if_duplicate=True)
			add_permission(source_dt_name, test_role, 0, ptype="read")
			add_permission(target_dt_name, test_role, 0, ptype="read")
			update_permission_property(
				target_dt_name, test_role, 1, "read", 0, validate=False
			)  # No permlevel 1 read
			test_user_doc.add_roles(test_role)

			# Test as the restricted user
			frappe.set_user(user.name)

			# Try filtering on permitted linked field (other_target_field - permlevel 0)
			try:
				frappe.qb.get_query(
					source_dt_name,
					filters={"link_field.other_target_field": "Public Data"},
					ignore_permissions=False,
					user=user.name,
				).run()
			except frappe.PermissionError as e:
				self.fail(f"Filtering on permitted linked field 'link_field.other_target_field' failed: {e}")

			# Try filtering on non-permitted linked field (target_field - permlevel 1)
			with self.assertRaises(frappe.PermissionError) as cm_link:
				frappe.qb.get_query(
					source_dt_name,
					filters={"link_field.target_field": "Secret Data"},
					ignore_permissions=False,
					user=user.name,
				).run()
			self.assertIn("You do not have permission to access field", str(cm_link.exception))
			self.assertIn(f"{target_dt_name}.target_field", str(cm_link.exception))

			# Cleanup
			frappe.set_user("Administrator")
			source_doc.delete(ignore_permissions=True)
			target_doc.delete(ignore_permissions=True)
			source_dt.delete()
			target_dt.delete()
			test_user_doc.remove_roles(test_role)
			frappe.delete_doc("Role", test_role, force=True)

	def test_dynamic_fields_in_group_by(self):
		"""Test dynamic field support in GROUP BY clause."""
		try:
			query = frappe.qb.get_query(
				"DocType",
				fields=["module.app_name", "name"],
				group_by="module.app_name",
			)
			result = query.run(as_dict=True)
			self.assertTrue(len(result) > 0)
			sql = query.get_sql()
			self.assertIn("LEFT JOIN", sql)
			self.assertIn("tabModule Def", sql)
		except Exception as e:
			self.fail(f"Dynamic link field in GROUP BY failed: {e}")

		note = frappe.get_doc(
			doctype="Note", title="Group By Test Note", seen_by=[{"user": "Administrator"}, {"user": "Guest"}]
		).insert()

		try:
			query = frappe.qb.get_query(
				"Note",
				fields=["seen_by.user", "name"],
				filters={"name": note.name},
				group_by="seen_by.user",
			)
			result = query.run(as_dict=True)
			self.assertTrue(len(result) >= 1)
			sql = query.get_sql()
			self.assertIn("LEFT JOIN", sql)
			self.assertIn("tabNote Seen By", sql)
		except Exception as e:
			self.fail(f"Dynamic child field in GROUP BY failed: {e}")
		finally:
			note.delete()

	def test_dynamic_fields_in_order_by(self):
		"""Test dynamic field support in ORDER BY clause."""
		try:
			query = frappe.qb.get_query(
				"DocType", fields=["name", "module.app_name"], order_by="module.app_name DESC", limit=5
			)
			result = query.run(as_dict=True)
			self.assertTrue(len(result) > 0)
			sql = query.get_sql()
			self.assertIn("LEFT JOIN", sql)
			self.assertIn("tabModule Def", sql)
			self.assertIn("ORDER BY", sql)
		except Exception as e:
			self.fail(f"Dynamic link field in ORDER BY failed: {e}")

		note1 = frappe.get_doc(
			doctype="Note", title="Order Test Note 1", seen_by=[{"user": "Administrator"}]
		).insert()
		note2 = frappe.get_doc(
			doctype="Note", title="Order Test Note 2", seen_by=[{"user": "Guest"}]
		).insert()

		try:
			query = frappe.qb.get_query(
				"Note",
				fields=["name", "seen_by.user"],
				filters={"name": ["in", [note1.name, note2.name]]},
				order_by="seen_by.user ASC",
			)
			result = query.run(as_dict=True)
			self.assertTrue(len(result) >= 2)
			sql = query.get_sql()
			self.assertIn("LEFT JOIN", sql)
			self.assertIn("tabNote Seen By", sql)
		except Exception as e:
			self.fail(f"Dynamic child field in ORDER BY failed: {e}")
		finally:
			note1.delete()
			note2.delete()

	def test_multiple_dynamic_fields_group_order(self):
		"""Test multiple dynamic fields in GROUP BY and ORDER BY."""
		try:
			query = frappe.qb.get_query(
				"DocType",
				fields=["module", "module.app_name", "name"],
				group_by="module, module.app_name",
				order_by="module.app_name",
			)
			result = query.run(as_dict=True)
			self.assertTrue(len(result) > 0)
		except Exception as e:
			self.fail(f"Multiple dynamic fields in GROUP BY/ORDER BY failed: {e}")

	def test_group_by_order_by_permission_checks(self):
		"""Test permission checks for dynamic fields in GROUP BY and ORDER BY."""
		target_dt_name = "TargetDocForGroupOrderPerm"
		source_dt_name = "SourceDocForGroupOrderPerm"
		test_role = "GroupOrderPermTestRole"
		test_user = "test2@example.com"

		frappe.set_user("Administrator")
		frappe.delete_doc("DocType", target_dt_name, ignore_missing=True, force=True)
		frappe.delete_doc("DocType", source_dt_name, ignore_missing=True, force=True)
		frappe.delete_doc("Role", test_role, ignore_missing=True, force=True)
		test_user_doc = frappe.get_doc("User", test_user)
		test_user_doc.remove_roles(test_role)

		target_dt = new_doctype(
			target_dt_name,
			fields=[
				{
					"fieldname": "restricted_field",
					"fieldtype": "Data",
					"permlevel": 1,
					"label": "Restricted Field",
				},
				{"fieldname": "public_field", "fieldtype": "Data", "label": "Public Field"},
			],
		).insert(ignore_if_duplicate=True)

		source_dt = new_doctype(
			source_dt_name,
			fields=[
				{
					"fieldname": "link_field",
					"fieldtype": "Link",
					"options": target_dt_name,
					"label": "Link Field",
				},
			],
		).insert(ignore_if_duplicate=True)

		frappe.get_doc({"doctype": "Role", "role_name": test_role}).insert(ignore_if_duplicate=True)
		add_permission(source_dt_name, test_role, 0, ptype="read")
		add_permission(target_dt_name, test_role, 0, ptype="read")
		update_permission_property(target_dt_name, test_role, 1, "read", 0, validate=False)
		test_user_doc.add_roles(test_role)

		frappe.set_user(test_user)

		try:
			frappe.qb.get_query(
				source_dt_name,
				fields=["link_field.public_field", "name"],
				group_by="link_field.public_field",
				ignore_permissions=False,
				user=test_user,
			).get_sql()
		except frappe.PermissionError as e:
			self.fail(f"GROUP BY with permitted field failed: {e}")

		with self.assertRaises(frappe.PermissionError) as cm:
			frappe.qb.get_query(
				source_dt_name,
				fields=["link_field.restricted_field", "name"],
				group_by="link_field.restricted_field",
				ignore_permissions=False,
				user=test_user,
			).get_sql()
		self.assertIn("You do not have permission to access field", str(cm.exception))
		self.assertIn("restricted_field", str(cm.exception))

		try:
			frappe.qb.get_query(
				source_dt_name,
				fields=["name", "link_field.public_field"],
				order_by="link_field.public_field",
				ignore_permissions=False,
				user=test_user,
			).get_sql()
		except frappe.PermissionError as e:
			self.fail(f"ORDER BY with permitted field failed: {e}")

		with self.assertRaises(frappe.PermissionError) as cm:
			frappe.qb.get_query(
				source_dt_name,
				fields=["name"],
				order_by="link_field.restricted_field",
				ignore_permissions=False,
				user=test_user,
			).get_sql()
		self.assertIn("You do not have permission to access field", str(cm.exception))
		self.assertIn("restricted_field", str(cm.exception))

		frappe.set_user("Administrator")
		source_dt.delete()
		target_dt.delete()
		test_user_doc.remove_roles(test_role)
		frappe.delete_doc("Role", test_role, force=True)

	def test_child_table_group_by_order_by_permissions(self):
		"""Test permission checks for child table fields in GROUP BY and ORDER BY."""
		child_dt_name = "ChildDocForGroupOrderPerm"
		parent_dt_name = "ParentDocForGroupOrderPerm"
		test_role = "ChildGroupOrderPermTestRole"
		test_user_email = "test2@example.com"

		frappe.set_user("Administrator")
		frappe.delete_doc("DocType", child_dt_name, ignore_missing=True, force=True)
		frappe.delete_doc("DocType", parent_dt_name, ignore_missing=True, force=True)
		frappe.delete_doc("Role", test_role, ignore_missing=True, force=True)

		test_user_doc = frappe.get_doc("User", test_user_email)
		test_user_doc.remove_roles(test_role)

		child_dt = new_doctype(
			child_dt_name,
			fields=[
				{
					"fieldname": "restricted_child_field",
					"fieldtype": "Data",
					"permlevel": 1,
					"label": "Restricted Child Field",
				},
				{"fieldname": "public_child_field", "fieldtype": "Data", "label": "Public Child Field"},
			],
			istable=1,
		).insert(ignore_if_duplicate=True)

		parent_dt = new_doctype(
			parent_dt_name,
			fields=[
				{
					"fieldname": "child_table",
					"fieldtype": "Table",
					"options": child_dt_name,
					"label": "Child Table",
				},
			],
		).insert(ignore_if_duplicate=True)

		frappe.get_doc({"doctype": "Role", "role_name": test_role}).insert(ignore_if_duplicate=True)
		add_permission(parent_dt_name, test_role, 0, ptype="read")
		add_permission(child_dt_name, test_role, 0, ptype="read")
		update_permission_property(child_dt_name, test_role, 1, "read", 0, validate=False)
		test_user_doc.add_roles(test_role)

		frappe.set_user(test_user_email)

		try:
			frappe.qb.get_query(
				parent_dt_name,
				fields=["child_table.public_child_field", "name"],
				group_by="child_table.public_child_field",
				ignore_permissions=False,
				user=test_user_email,
			).get_sql()
		except frappe.PermissionError as e:
			self.fail(f"GROUP BY with permitted child field failed: {e}")

		with self.assertRaises(frappe.PermissionError) as cm:
			frappe.qb.get_query(
				parent_dt_name,
				fields=["child_table.restricted_child_field", "name"],
				group_by="child_table.restricted_child_field",
				ignore_permissions=False,
				user=test_user_email,
			).get_sql()
		self.assertIn("You do not have permission to access field", str(cm.exception))
		self.assertIn("restricted_child_field", str(cm.exception))

		with self.assertRaises(frappe.PermissionError) as cm:
			frappe.qb.get_query(
				parent_dt_name,
				fields=["name"],
				order_by="child_table.restricted_child_field",
				ignore_permissions=False,
				user=test_user_email,
			).get_sql()
		self.assertIn("You do not have permission to access field", str(cm.exception))
		self.assertIn("restricted_child_field", str(cm.exception))

		frappe.set_user("Administrator")
		parent_dt.delete()
		child_dt.delete()
		test_user_doc.remove_roles(test_role)
		frappe.delete_doc("Role", test_role, force=True)

	def test_group_by_order_by_validation_errors(self):
		"""Test validation errors for invalid GROUP BY and ORDER BY fields."""
		invalid_group_by_fields = [
			"name; DROP TABLE users",
			"name--comment",
			"name /* comment */",
			"invalid-field-name",
			"field with space",
			"`field with space`",
			"name, email; SELECT 1",
		]

		for field in invalid_group_by_fields:
			with self.assertRaises(
				frappe.ValidationError, msg=f"Invalid GROUP BY field '{field}' passed validation"
			):
				frappe.qb.get_query("User", group_by=field).get_sql()

		invalid_order_by_fields = [
			"name sideways",
			"name INVALID_DIRECTION",
			"name ASC;",
			"name, email; SELECT 1",
		]

		for field in invalid_order_by_fields:
			with self.assertRaises(
				(frappe.ValidationError, ValueError),
				msg=f"Invalid ORDER BY field '{field}' passed validation",
			):
				frappe.qb.get_query("User", order_by=field).get_sql()

	def test_backtick_rejection_group_order(self):
		"""Test that backticks are properly rejected in GROUP BY and ORDER BY."""
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", group_by="`name`").get_sql()
		self.assertIn("cannot contain backticks", str(cm.exception))

		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", order_by="`name` ASC").get_sql()
		self.assertIn("cannot contain backticks", str(cm.exception))

		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", group_by="`name`, `email`").get_sql()
		self.assertIn("cannot contain backticks", str(cm.exception))

	def test_sql_functions_in_fields(self):
		"""Test SQL function support in fields with various syntaxes."""

		# Test simple function without alias
		query = frappe.qb.get_query("User", fields=["user_type", {"COUNT": "name"}], group_by="user_type")
		sql = query.get_sql()
		self.assertIn("COUNT(`name`)", sql)
		self.assertIn("GROUP BY", sql)

		# Test function with alias
		query = frappe.qb.get_query(
			"User", fields=[{"COUNT": "name", "as": "total_users"}], group_by="user_type"
		)
		sql = query.get_sql()
		self.assertIn("COUNT(`name`) `total_users`", sql)

		# Test SUM function with alias
		query = frappe.qb.get_query(
			"User", fields=[{"SUM": "enabled", "as": "total_enabled"}], group_by="user_type"
		)
		sql = query.get_sql()
		self.assertIn("SUM(`enabled`) `total_enabled`", sql)

		# Test MAX function
		query = frappe.qb.get_query(
			"User", fields=[{"MAX": "creation", "as": "latest_user"}], group_by="user_type"
		)
		sql = query.get_sql()
		self.assertIn("MAX(`creation`) `latest_user`", sql)

		# Test MIN function
		query = frappe.qb.get_query(
			"User", fields=[{"MIN": "creation", "as": "earliest_user"}], group_by="user_type"
		)
		sql = query.get_sql()
		self.assertIn("MIN(`creation`) `earliest_user`", sql)

		# Test AVG function
		query = frappe.qb.get_query(
			"User", fields=[{"AVG": "enabled", "as": "avg_enabled"}], group_by="user_type"
		)
		sql = query.get_sql()
		self.assertIn("AVG(`enabled`) `avg_enabled`", sql)

		# Test ABS function
		query = frappe.qb.get_query("User", fields=[{"ABS": "enabled", "as": "abs_enabled"}])
		sql = query.get_sql()
		self.assertIn("ABS(`enabled`) `abs_enabled`", sql)

		# Test IFNULL function with two parameters
		query = frappe.qb.get_query(
			"User", fields=[{"IFNULL": ["first_name", "'Unknown'"], "as": "safe_name"}]
		)
		sql = query.get_sql()
		self.assertIn("IFNULL(`first_name`,'Unknown') `safe_name`", sql)

		# Test TIMESTAMP function
		query = frappe.qb.get_query("User", fields=[{"TIMESTAMP": "creation", "as": "ts"}])
		sql = query.get_sql()
		self.assertIn("TIMESTAMP(`creation`) `ts`", sql)

		# Test mixed regular fields and function fields
		query = frappe.qb.get_query(
			"User",
			fields=[
				"user_type",
				{"COUNT": "name", "as": "total_users"},
				{"MAX": "creation", "as": "latest_creation"},
			],
			group_by="user_type",
		)
		sql = query.get_sql()
		self.assertIn("`user_type`", sql)
		self.assertIn("COUNT(`name`) `total_users`", sql)
		self.assertIn("MAX(`creation`) `latest_creation`", sql)

		# Test NOW function with no arguments
		query = frappe.qb.get_query("User", fields=[{"NOW": None, "as": "current_time"}])
		sql = query.get_sql()
		self.assertIn("NOW() `current_time`", sql)

		# Test CONCAT function (which is supported)
		query = frappe.qb.get_query(
			"User", fields=[{"CONCAT": ["first_name", "last_name"], "as": "full_name"}]
		)
		sql = query.get_sql()
		self.assertIn("CONCAT(`first_name`,`last_name`) `full_name`", sql)

		# Test unsupported function validation
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", fields=[{"UNSUPPORTED_FUNC": "name"}]).get_sql()
		self.assertIn("Unsupported function or invalid field name: UNSUPPORTED_FUNC", str(cm.exception))

		# Test unsupported function that might be confused with child field
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", fields=[{"UPPER": ["first_name"]}]).get_sql()
		self.assertIn("Unsupported function or invalid field name: UPPER", str(cm.exception))

		# Test SQL injection attempt
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.qb.get_query("User", fields=[{"DROP": "TABLE users"}]).get_sql()
		self.assertIn("Unsupported function or invalid field name: DROP", str(cm.exception))


# This function is used as a permission query condition hook
def test_permission_hook_condition(user):
	return "`tabDashboard Settings`.`name` = 'Administrator'"
