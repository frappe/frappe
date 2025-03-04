import itertools

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.query_builder import Field
from frappe.query_builder.functions import Abs, Count, Ifnull, Max, Now, Timestamp
from frappe.tests import IntegrationTestCase
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
			"SELECT `tabDocType`.* FROM `tabDocType` LEFT JOIN `tabDocField` ON `tabDocField`.`parent`=`tabDocType`.`name` AND `tabDocField`.`parenttype`='DocType' WHERE `tabDocField`.`name` LIKE 'f%' AND `tabDocType`.`parent`='something'",
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
			frappe.qb.get_query(
				"User", fields=["`tabUser`.`name`, Count(`name`) as count"], filters={"name": "Administrator"}
			).run(),
			frappe.qb.from_("User")
			.select(Field("name"), Count("name").as_("count"))
			.where(Field("name") == "Administrator")
			.run(),
		)

		self.assertEqual(
			frappe.qb.get_query(
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
			frappe.qb.get_query(
				"User", fields="`tabUser`.`name`, Count(`name`) as `count`", filters={"name": "Administrator"}
			).run(),
			frappe.qb.from_("User")
			.select(Field("name"), Count("name").as_("count"))
			.where(Field("name") == "Administrator")
			.run(),
		)

	def test_functions_fields(self):
		self.assertEqual(
			frappe.qb.get_query("User", fields="Count(name)", filters={}).get_sql(),
			frappe.qb.from_("User").select(Count(Field("name"))).get_sql(),
		)

		self.assertEqual(
			frappe.qb.get_query("User", fields=["Count(name)", "Max(name)"], filters={}).get_sql(),
			frappe.qb.from_("User").select(Count(Field("name")), Max(Field("name"))).get_sql(),
		)

		self.assertEqual(
			frappe.qb.get_query("User", fields=["abs(name-email)", "Count(name)"], filters={}).get_sql(),
			frappe.qb.from_("User")
			.select(Abs(Field("name") - Field("email")), Count(Field("name")))
			.get_sql(),
		)

		self.assertEqual(
			frappe.qb.get_query("User", fields=[Count("*")], filters={}).get_sql(),
			frappe.qb.from_("User").select(Count("*")).get_sql(),
		)

		self.assertEqual(
			frappe.qb.get_query("User", fields="timestamp(creation, modified)", filters={}).get_sql(),
			frappe.qb.from_("User").select(Timestamp(Field("creation"), Field("modified"))).get_sql(),
		)

		self.assertEqual(
			frappe.qb.get_query(
				"User", fields="Count(name) as count, Max(email) as max_email", filters={}
			).get_sql(),
			frappe.qb.from_("User")
			.select(Count(Field("name")).as_("count"), Max(Field("email")).as_("max_email"))
			.get_sql(),
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

		self.assertEqual(
			frappe.qb.get_query(
				user_doctype, fields=["Count(name) as count", "email as id"], filters={}
			).get_sql(),
			frappe.qb.from_(user_doctype)
			.select(Count(Field("name")).as_("count"), user_doctype.email.as_("id"))
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
			"SELECT `tabDocType`.`name` FROM `tabDocType` LEFT JOIN `tabDocPerm` ON `tabDocPerm`.`parent`=`tabDocType`.`name` AND `tabDocPerm`.`parenttype`='DocType' WHERE `tabDocPerm`.`role`='System Manager'".replace(
				"`", '"' if frappe.db.db_type == "postgres" else "`"
			),
		)

		self.assertRaisesRegex(
			frappe.PermissionError,
			"Invalid filter",
			lambda: frappe.qb.get_query(
				"DocType",
				fields=["name"],
				filters={"permissions.role": "System Manager"},
				validate_filters=True,
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

		self.assertEqual(
			frappe.qb.get_query(
				"Note",
				filters={"name": "Test Note Title"},
				fields=["name", "seen_by.user as seen_by", "`tabNote Seen By`.`idx` as idx"],
			).get_sql(),
			"SELECT `tabNote`.`name`,`tabNote Seen By`.`user` `seen_by`,`tabNote Seen By`.`idx` `idx` FROM `tabNote` LEFT JOIN `tabNote Seen By` ON `tabNote Seen By`.`parent`=`tabNote`.`name` AND `tabNote Seen By`.`parenttype`='Note' WHERE `tabNote`.`name`='Test Note Title'".replace(
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

	@run_only_if(db_type_is.MARIADB)
	def test_comment_stripping(self):
		self.assertNotIn(
			"email", frappe.qb.get_query("User", fields=["name", "#email"], filters={}).get_sql()
		)

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

		query = frappe.qb.get_query("Dashboard Settings", user=self.user, ignore_permissions=False)
		self.assertIn(f'`tabDashboard Settings`.`user` = "{self.user}"', str(query))

		# Cleanup
		script.delete()
		frappe.clear_cache()
		frappe.hooks.permission_query_conditions = original_hooks


# This function is used as a permission query condition hook
def test_permission_hook_condition(user):
	return "`tabDashboard Settings`.`name` = 'Administrator'"
