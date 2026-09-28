# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Use blog post test to test user permissions logic"""

from unittest.mock import patch

import frappe
import frappe.defaults
import frappe.model.meta
import frappe.permissions
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.core.doctype.user_permission.user_permission import clear_user_permissions
from frappe.core.page.permission_manager.permission_manager import add, remove, reset, update
from frappe.desk.form.load import getdoc
from frappe.installer import _delete_doctypes
from frappe.permissions import (
	ALL_USER_ROLE,
	AUTOMATIC_ROLES,
	GUEST_ROLE,
	SYSTEM_USER_ROLE,
	add_permission,
	add_user_permission,
	clear_user_permissions_for_doctype,
	get_doc_permissions,
	get_doctypes_with_read,
	remove_user_permission,
	update_permission_property,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.test_helpers import setup_for_tests
from frappe.tests.utils import make_test_records_for_doctype
from frappe.utils.data import now_datetime
from frappe.utils.user import UserPermissions

EXTRA_TEST_RECORD_DEPENDENCIES = ["User", "Contact", "Salutation"]


def nested_root_scope_condition(user, doctype):
	return f"`tab{doctype}`.`scope` = {frappe.db.escape('allowed')}"


class TestPermissions(IntegrationTestCase):
	def test_nested_child_query_respects_root_user_permission(self):
		frappe.set_user("Administrator")
		grandchild_dt = new_doctype(istable=1).insert().name
		child_dt = (
			new_doctype(
				istable=1,
				fields=[
					{
						"label": "Details",
						"fieldname": "details",
						"fieldtype": "Table",
						"options": grandchild_dt,
					}
				],
			)
			.insert()
			.name
		)
		root_dt = (
			new_doctype(
				fields=[
					{"label": "Assignee", "fieldname": "assignee", "fieldtype": "Link", "options": "User"},
					{"label": "Rows", "fieldname": "rows", "fieldtype": "Table", "options": child_dt},
				],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)
		for assignee, value in (("test1@example.com", "allowed"), ("Administrator", "denied")):
			frappe.get_doc(
				{
					"doctype": root_dt,
					"assignee": assignee,
					"rows": [{"details": [{"some_fieldname": value}]}],
				}
			).insert()
		add_user_permission("User", "test1@example.com", "test1@example.com", applicable_for=root_dt)
		frappe.set_user("test1@example.com")
		rows = frappe.get_list(grandchild_dt, fields=["some_fieldname"], parent_doctype=child_dt)
		self.assertEqual([row.some_fieldname for row in rows], ["allowed"])

	def test_nested_child_query_respects_root_permission_hook(self):
		frappe.set_user("Administrator")
		grandchild_dt = new_doctype(istable=1).insert().name
		child_dt = (
			new_doctype(
				istable=1,
				fields=[
					{
						"label": "Details",
						"fieldname": "details",
						"fieldtype": "Table",
						"options": grandchild_dt,
					}
				],
			)
			.insert()
			.name
		)
		root_dt = (
			new_doctype(
				fields=[
					{"label": "Scope", "fieldname": "scope", "fieldtype": "Data"},
					{"label": "Rows", "fieldname": "rows", "fieldtype": "Table", "options": child_dt},
				],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)
		for scope in ("allowed", "denied"):
			frappe.get_doc(
				{
					"doctype": root_dt,
					"scope": scope,
					"rows": [{"details": [{"some_fieldname": scope}]}],
				}
			).insert()
		original_get_hooks = frappe.get_hooks

		def get_hooks_with_scope(key=None, *args, **kwargs):
			if key == "permission_query_conditions":
				return {root_dt: ["frappe.tests.test_permissions.nested_root_scope_condition"]}
			return original_get_hooks(key, *args, **kwargs)

		frappe.set_user("test1@example.com")
		with patch.object(frappe, "get_hooks", get_hooks_with_scope):
			rows = frappe.get_list(grandchild_dt, fields=["some_fieldname"], parent_doctype=child_dt)
		self.assertEqual([row.some_fieldname for row in rows], ["allowed"])

	def test_child_query_excludes_private_root_table(self):
		frappe.set_user("Administrator")
		child_dt = new_doctype(istable=1).insert().name
		root_dt = (
			new_doctype(
				fields=[
					{
						"label": "Public Rows",
						"fieldname": "public_rows",
						"fieldtype": "Table",
						"options": child_dt,
					},
					{
						"label": "Private Rows",
						"fieldname": "private_rows",
						"fieldtype": "Table",
						"options": child_dt,
						"permlevel": 1,
					},
				],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)
		frappe.get_doc(
			{
				"doctype": root_dt,
				"public_rows": [{"some_fieldname": "visible"}],
				"private_rows": [{"some_fieldname": "secret"}],
			}
		).insert()
		frappe.set_user("test1@example.com")
		rows = frappe.get_list(child_dt, fields=["some_fieldname"], parent_doctype=root_dt)
		self.assertEqual([row.some_fieldname for row in rows], ["visible"])

	def test_single_child_query_excludes_private_table(self):
		frappe.set_user("Administrator")
		child_dt = new_doctype(istable=1).insert().name
		root_dt = (
			new_doctype(
				issingle=1,
				fields=[
					{
						"label": "Public Rows",
						"fieldname": "public_rows",
						"fieldtype": "Table",
						"options": child_dt,
					},
					{
						"label": "Private Rows",
						"fieldname": "private_rows",
						"fieldtype": "Table",
						"options": child_dt,
						"permlevel": 1,
					},
				],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)
		frappe.get_doc(
			{
				"doctype": root_dt,
				"public_rows": [{"some_fieldname": "visible"}],
				"private_rows": [{"some_fieldname": "secret"}],
			}
		).save()
		frappe.set_user("test1@example.com")
		rows = frappe.get_list(child_dt, fields=["some_fieldname"], parent_doctype=root_dt)
		self.assertEqual([row.some_fieldname for row in rows], ["visible"])

	def test_nested_child_query_under_single_root(self):
		frappe.set_user("Administrator")
		grandchild_dt = new_doctype(istable=1).insert().name
		child_dt = (
			new_doctype(
				istable=1,
				fields=[
					{
						"label": "Details",
						"fieldname": "details",
						"fieldtype": "Table",
						"options": grandchild_dt,
					}
				],
			)
			.insert()
			.name
		)
		root_dt = (
			new_doctype(
				issingle=1,
				fields=[{"label": "Rows", "fieldname": "rows", "fieldtype": "Table", "options": child_dt}],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)
		frappe.get_doc({"doctype": root_dt, "rows": [{"details": [{"some_fieldname": "visible"}]}]}).save()
		frappe.set_user("test1@example.com")
		rows = frappe.get_list(grandchild_dt, fields=["some_fieldname"], parent_doctype=child_dt)
		self.assertEqual([row.some_fieldname for row in rows], ["visible"])

	def test_nested_child_tab_notation_excludes_private_table(self):
		frappe.set_user("Administrator")
		grandchild_dt = (
			new_doctype(
				istable=1,
				fields=[
					{"label": "Value", "fieldname": "some_fieldname", "fieldtype": "Data"},
					{"label": "Secret", "fieldname": "secret", "fieldtype": "Data", "mask": 1},
				],
			)
			.insert()
			.name
		)
		child_dt = (
			new_doctype(
				istable=1,
				fields=[
					{
						"label": "Public",
						"fieldname": "public",
						"fieldtype": "Table",
						"options": grandchild_dt,
					},
					{
						"label": "Private",
						"fieldname": "private",
						"fieldtype": "Table",
						"options": grandchild_dt,
						"permlevel": 1,
					},
				],
			)
			.insert()
			.name
		)
		root_dt = (
			new_doctype(
				fields=[{"label": "Rows", "fieldname": "rows", "fieldtype": "Table", "options": child_dt}],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)
		frappe.get_doc(
			{
				"doctype": root_dt,
				"rows": [
					{
						"public": [{"some_fieldname": "visible", "secret": "public secret"}],
						"private": [{"some_fieldname": "secret", "secret": "private secret"}],
					}
				],
			}
		).insert()
		frappe.set_user("test1@example.com")
		rows = frappe.get_list(
			child_dt,
			fields=[f"`tab{grandchild_dt}`.`some_fieldname` as value"],
			parent_doctype=root_dt,
		)
		self.assertEqual([row.value for row in rows], ["visible"])
		masked_rows = frappe.get_list(
			child_dt,
			fields=[f"`tab{grandchild_dt}`.`secret` as exposed_secret"],
			parent_doctype=root_dt,
		)
		self.assertEqual([row.exposed_secret for row in masked_rows], ["XXXXXXXX"])
		masked_tuples = frappe.get_list(
			child_dt,
			fields=[f"`tab{grandchild_dt}`.`secret` as exposed_secret"],
			parent_doctype=root_dt,
			as_list=True,
		)
		self.assertEqual(masked_tuples, [("XXXXXXXX",)])
		masked_values = frappe.get_list(
			child_dt,
			fields=[f"`tab{grandchild_dt}`.`secret` as exposed_secret"],
			parent_doctype=root_dt,
			pluck="exposed_secret",
		)
		self.assertEqual(masked_values, ["XXXXXXXX"])

	def test_nested_child_permissions_and_query(self):
		frappe.set_user("Administrator")
		grandchild_dt = (
			new_doctype(
				istable=1,
				fields=[
					{"label": "Value", "fieldname": "some_fieldname", "fieldtype": "Data"},
					{"label": "Secret", "fieldname": "secret", "fieldtype": "Data", "mask": 1},
					{"label": "Restricted", "fieldname": "restricted", "fieldtype": "Data", "permlevel": 1},
				],
			)
			.insert()
			.name
		)
		child_dt = (
			new_doctype(
				istable=1,
				fields=[
					{
						"label": "Details",
						"fieldname": "details",
						"fieldtype": "Table",
						"options": grandchild_dt,
					},
					{
						"label": "Private Details",
						"fieldname": "private_details",
						"fieldtype": "Table",
						"options": grandchild_dt,
						"permlevel": 1,
					},
				],
			)
			.insert()
			.name
		)
		root_dt = (
			new_doctype(
				fields=[{"label": "Rows", "fieldname": "rows", "fieldtype": "Table", "options": child_dt}],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)
		root = frappe.get_doc(
			{
				"doctype": root_dt,
				"rows": [
					{
						"details": [
							{"some_fieldname": "visible", "secret": "hidden", "restricted": "classified"}
						]
					}
				],
			}
		).insert()
		grandchild_name = root.rows[0].details[0].name

		frappe.set_user("test1@example.com")
		grandchild = frappe.get_doc(grandchild_dt, grandchild_name)
		self.assertTrue(grandchild.has_permission("read"))
		self.assertTrue(grandchild.has_permission("write"))
		rows = frappe.get_list(
			child_dt,
			fields=["name", {"details": ["some_fieldname", "secret"]}],
			parent_doctype=root_dt,
		)
		self.assertEqual(rows[0].details[0].some_fieldname, "visible")
		self.assertEqual(rows[0].details[0].secret, "XXXXXXXX")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list(
				child_dt,
				fields=["name"],
				filters={"details.restricted": "classified"},
				parent_doctype=root_dt,
			)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list(child_dt, order_by="details.restricted asc", parent_doctype=root_dt)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list(
				child_dt,
				filters={"private_details.some_fieldname": "guess"},
				parent_doctype=root_dt,
			)
		details = frappe.get_list(
			grandchild_dt,
			fields=["name", "some_fieldname", "secret"],
			parent_doctype=child_dt,
		)
		self.assertEqual([row.name for row in details], [grandchild_name])
		self.assertEqual(details[0].some_fieldname, "visible")
		self.assertEqual(details[0].secret, "XXXXXXXX")
		aliased_details = frappe.get_list(
			grandchild_dt,
			fields=["secret as exposed_secret"],
			parent_doctype=child_dt,
		)
		self.assertEqual(aliased_details[0].exposed_secret, "XXXXXXXX")
		self.assertEqual(
			frappe.get_list(
				grandchild_dt,
				fields=["secret as exposed_secret"],
				parent_doctype=child_dt,
				as_list=True,
			),
			[("XXXXXXXX",)],
		)
		root_for_edit = frappe.get_doc(root_dt, root.name)
		root_for_edit.apply_fieldlevel_read_permissions()
		self.assertEqual(root_for_edit.rows[0].details[0].secret, "XXXXXXXX")
		root_for_edit.save()
		self.assertEqual(frappe.db.get_value(grandchild_dt, grandchild_name, "secret"), "hidden")
		grandchild.reload()
		grandchild.restricted = "changed"
		grandchild.save()
		self.assertEqual(frappe.db.get_value(grandchild_dt, grandchild_name, "restricted"), "classified")
		grandchild.parent = "nonexistent"
		self.assertFalse(grandchild.has_permission("read"))
		grandchild.parent = root.rows[0].name
		grandchild.parentfield = "wrong_field"
		self.assertFalse(grandchild.has_permission("read"))
		grandchild.parentfield = "details"
		child_name = root.rows[0].name
		frappe.db.set_value(
			child_dt,
			child_name,
			{"parent": child_name, "parenttype": child_dt, "parentfield": "details"},
			update_modified=False,
		)
		try:
			self.assertFalse(frappe.get_doc(grandchild_dt, grandchild_name).has_permission("read"))
		finally:
			frappe.db.set_value(
				child_dt,
				child_name,
				{"parent": root.name, "parenttype": root_dt, "parentfield": "rows"},
				update_modified=False,
			)
		owned_root = frappe.get_doc(
			{"doctype": root_dt, "rows": [{"details": [{"some_fieldname": "owned"}]}]}
		).insert()
		frappe.db.set_value("DocPerm", {"parent": root_dt, "role": "System Manager"}, "if_owner", 1)
		frappe.clear_cache(doctype=root_dt)
		self.assertEqual(
			[row.name for row in frappe.get_list(grandchild_dt, parent_doctype=child_dt)],
			[owned_root.rows[0].details[0].name],
		)

		frappe.set_user("test3@example.com")
		self.assertFalse(frappe.get_doc(grandchild_dt, grandchild_name).has_permission("read"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list(
				child_dt, fields=["name", {"details": ["some_fieldname"]}], parent_doctype=root_dt
			)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list(grandchild_dt, fields=["name"], parent_doctype=child_dt)
		frappe.set_user("Administrator")
		frappe.share.add(root_dt, root.name, "test3@example.com", read=1)
		frappe.set_user("test3@example.com")
		self.assertEqual(
			[row.name for row in frappe.get_list(grandchild_dt, parent_doctype=child_dt)],
			[grandchild_name],
		)
		frappe.set_user("Administrator")
		other_root_dt = (
			new_doctype(
				fields=[{"label": "Rows", "fieldname": "rows", "fieldtype": "Table", "options": child_dt}],
				permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)
		other_root = frappe.get_doc(
			{"doctype": other_root_dt, "rows": [{"details": [{"some_fieldname": "other root"}]}]}
		).insert()
		frappe.set_user("test3@example.com")
		forged = frappe.get_doc(grandchild_dt, grandchild_name)
		forged.parent = other_root.rows[0].name
		self.assertFalse(forged.has_permission("read"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list(grandchild_dt, parent_doctype=child_dt)
		self.assertEqual(
			[
				row.name
				for row in frappe.get_list(grandchild_dt, parent_doctype=child_dt, root_doctype=root_dt)
			],
			[grandchild_name],
		)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list(grandchild_dt, parent_doctype=child_dt, root_doctype=other_root_dt)

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_for_tests()
		frappe.clear_cache(doctype="Test Blog Post")
		user = frappe.get_doc("User", "test1@example.com")
		user.add_roles("Website Manager")
		user.add_roles("System Manager")

		user = frappe.get_doc("User", "test2@example.com")
		user.add_roles("Blogger")

		user = frappe.get_doc("User", "test3@example.com")
		user.add_roles("Sales User")

		user = frappe.get_doc("User", "testperm@example.com")
		user.add_roles("Website Manager")

	def setUp(self):
		frappe.clear_cache(doctype="Test Blog Post")

		reset("Test Blogger")
		reset("Test Blog Post")

		frappe.db.delete("User Permission")

		frappe.set_user("test1@example.com")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Test Blogger", "_Test Blogger 1", "user", None)

		clear_user_permissions_for_doctype("Test Blog Category")
		clear_user_permissions_for_doctype("Test Blog Post")
		clear_user_permissions_for_doctype("Test Blogger")

	@staticmethod
	def set_strict_user_permissions(ignore):
		ss = frappe.get_doc("System Settings")
		ss.apply_strict_user_permissions = ignore
		ss.flags.ignore_mandatory = 1
		ss.save()

	def test_basic_permission(self):
		post = frappe.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertTrue(post.has_permission("read"))

	def test_select_permission(self):
		# grant only select perm to blog post
		add_permission("Test Blog Post", "Sales User", 0)
		update_permission_property("Test Blog Post", "Sales User", 0, "select", 1)
		update_permission_property("Test Blog Post", "Sales User", 0, "read", 0)
		update_permission_property("Test Blog Post", "Sales User", 0, "write", 0)

		frappe.clear_cache(doctype="Test Blog Post")
		frappe.set_user("test3@example.com")

		# validate select perm
		post = frappe.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertTrue(post.has_permission("select"))

		# validate does not have read and write perm
		self.assertFalse(post.has_permission("read"))
		self.assertRaises(frappe.PermissionError, post.save)

		permitted_record = frappe.get_list("Test Blog Post", fields="*", limit=1)[0]
		full_record = frappe.get_all("Test Blog Post", fields="*", limit=1)[0]
		self.assertNotEqual(permitted_record, full_record)
		self.assertSequenceSubset(post.meta.default_fields + post.meta.get_search_fields(), permitted_record)

	def test_owner_only_export_stays_in_can_export(self):
		role_name = "Test Export Boot Role"
		user_name = "test_export_boot@example.com"
		owner_only_dt = "Test Owner Only Export Boot"
		shared_dt = "Test Shared Export Boot"

		frappe.set_user("Administrator")
		frappe.delete_doc("User", user_name, ignore_missing=True, force=True)
		for name in (owner_only_dt, shared_dt):
			frappe.delete_doc("DocType", name, ignore_missing=True, force=True)
		frappe.delete_doc("Role", role_name, ignore_missing=True, force=True)

		def boot_perms():
			frappe.clear_cache(user=user_name)
			frappe.set_user(user_name)
			perms = UserPermissions()
			perms.build_permissions()
			frappe.set_user("Administrator")
			return perms

		try:
			frappe.get_doc(doctype="Role", role_name=role_name, desk_access=1).insert()

			for name, if_owner in ((owner_only_dt, 1), (shared_dt, 0)):
				new_doctype(
					name,
					fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title"}],
					permissions=[{"role": role_name, "read": 1, "export": 1, "if_owner": if_owner}],
				).insert()

			user = frappe.get_doc(
				doctype="User", email=user_name, first_name="Export Boot", send_welcome_email=0
			).insert()
			user.add_roles(role_name)

			perms = boot_perms()
			self.assertIn(owner_only_dt, perms.can_export)
			self.assertIn(owner_only_dt, perms.can_export_owner_only)
			self.assertIn(shared_dt, perms.can_export)
			self.assertNotIn(shared_dt, perms.can_export_owner_only)

			user.add_roles("System Manager")
			perms = boot_perms()
			self.assertNotIn(owner_only_dt, perms.can_export_owner_only)
		finally:
			frappe.set_user("Administrator")
			frappe.delete_doc("User", user_name, ignore_missing=True, force=True)
			frappe.delete_doc("Role", role_name, ignore_missing=True, force=True)
			for name in (owner_only_dt, shared_dt):
				frappe.delete_doc("DocType", name, ignore_missing=True, force=True)
			frappe.db.commit()

	def test_user_permissions_in_doc(self):
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")

		post = frappe.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertFalse(post.has_permission("read"))
		self.assertFalse(get_doc_permissions(post).get("read"))

		post1 = frappe.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertTrue(post1.has_permission("read"))
		self.assertTrue(get_doc_permissions(post1).get("read"))

	def test_user_permission_denial_is_explained(self):
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		with self.set_user("test2@example.com"):
			frappe.local.message_log = []
			post = frappe.get_doc("Test Blog Post", "_Test Blog Post")
			self.assertRaises(frappe.PermissionError, post.check_permission, "read")

			message = frappe.local.message_log[-1]["message"]
			self.assertIn("Test Blog Category", message)
			self.assertIn("_Test Blog Category", message)

	def test_user_permissions_in_report(self):
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		names = [d.name for d in frappe.get_list("Test Blog Post", fields=["name", "blog_category"])]

		self.assertTrue("_Test Blog Post 1" in names)
		self.assertFalse("_Test Blog Post" in names)

	def test_user_permissions_in_report_with_multiple_link_fields(self):
		from frappe.desk.query_report import get_user_match_filters

		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")
		add_user_permission("Test Blogger", "_Test Blogger 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		match_filters = get_user_match_filters(["Test Blog Post"], "test2@example.com")

		filter_list = match_filters["Test Blog Post"]
		self.assertEqual(len(filter_list), 1)
		self.assertEqual(
			filter_list[0],
			{
				"Test Blog Category": ["_Test Blog Category 1"],
				"Test Blogger": ["_Test Blogger 1"],
			},
		)

	def test_default_values(self):
		doc = frappe.new_doc("Test Blog Post")
		self.assertFalse(doc.get("blog_category"))

		# Fetch default based on single user permission
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.new_doc("Test Blog Post")
		self.assertEqual(doc.get("blog_category"), "_Test Blog Category 1")

		# Don't fetch default if user permissions is more than 1
		add_user_permission(
			"Test Blog Category", "_Test Blog Category", "test2@example.com", ignore_permissions=True
		)
		frappe.clear_cache()
		doc = frappe.new_doc("Test Blog Post")
		self.assertFalse(doc.get("blog_category"))

		# Fetch user permission set as default from multiple user permission
		add_user_permission(
			"Test Blog Category",
			"_Test Blog Category 2",
			"test2@example.com",
			ignore_permissions=True,
			is_default=1,
		)
		frappe.clear_cache()
		doc = frappe.new_doc("Test Blog Post")
		self.assertEqual(doc.get("blog_category"), "_Test Blog Category 2")

	def test_user_link_match_doc(self):
		blogger = frappe.get_doc("Test Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()
		frappe.permissions.add_user_permission("Test Blogger", blogger.name, blogger.user)

		frappe.set_user("test2@example.com")

		post = frappe.get_doc("Test Blog Post", "_Test Blog Post 2")
		self.assertTrue(post.has_permission("read"))
		post1 = frappe.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertFalse(post1.has_permission("read"))

	def test_user_link_match_report(self):
		blogger = frappe.get_doc("Test Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()
		frappe.permissions.add_user_permission("Test Blogger", blogger.name, blogger.user)

		frappe.set_user("test2@example.com")

		names = [d.name for d in frappe.get_list("Test Blog Post", fields=["name", "owner"])]
		self.assertTrue("_Test Blog Post 2" in names)
		self.assertFalse("_Test Blog Post 1" in names)

	def test_set_user_permissions(self):
		frappe.set_user("test1@example.com")
		add_user_permission("Test Blog Post", "_Test Blog Post", "test2@example.com")

	def test_not_allowed_to_set_user_permissions(self):
		frappe.set_user("test2@example.com")

		# this user can't add user permissions
		self.assertRaises(
			frappe.PermissionError,
			add_user_permission,
			"Test Blog Post",
			"_Test Blog Post",
			"test2@example.com",
		)

	def test_read_if_explicit_user_permissions_are_set(self):
		self.test_set_user_permissions()

		frappe.set_user("test2@example.com")

		# user can only access permitted blog post
		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertTrue(doc.has_permission("read"))

		# and not this one
		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertFalse(doc.has_permission("read"))

	def test_not_allowed_to_remove_user_permissions(self):
		self.test_set_user_permissions()

		frappe.set_user("test2@example.com")

		# user cannot remove their own user permissions
		self.assertRaises(
			frappe.PermissionError,
			remove_user_permission,
			"Test Blog Post",
			"_Test Blog Post",
			"test2@example.com",
		)

	def test_user_permissions_if_applied_on_doc_being_evaluated(self):
		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertTrue(doc.has_permission("read"))

		frappe.set_user("test1@example.com")
		add_user_permission("Test Blog Post", "_Test Blog Post", "test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertFalse(doc.has_permission("read"))

		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertTrue(doc.has_permission("read"))

	def test_set_standard_fields_manually(self):
		# check that creation and owner cannot be set manually
		from datetime import timedelta

		fake_creation = now_datetime() + timedelta(days=-7)
		fake_owner = frappe.db.get_value("User", {"name": ("!=", frappe.session.user)})

		d = frappe.new_doc("ToDo")
		d.description = "ToDo created via test_set_standard_fields_manually"
		d.creation = fake_creation
		d.owner = fake_owner
		d.save()
		self.assertNotEqual(d.creation, fake_creation)
		self.assertNotEqual(d.owner, fake_owner)

	def test_dont_change_standard_constants(self):
		# check that Document.creation cannot be changed
		user = frappe.get_doc("User", frappe.session.user)
		user.creation = now_datetime()
		self.assertRaises(frappe.CannotChangeConstantError, user.save)

		# check that Document.owner cannot be changed
		user.reload()
		user.owner = "Guest"
		self.assertRaises(frappe.CannotChangeConstantError, user.save)

	def test_set_only_once(self):
		blog_post = frappe.get_meta("Test Blog Post")
		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post 1")
		doc.db_set("title", "Old")
		blog_post.get_field("title").set_only_once = 1
		doc.title = "New"
		self.assertRaises(frappe.CannotChangeConstantError, doc.save)
		blog_post.get_field("title").set_only_once = 0

	def test_set_only_once_child_table_rows(self):
		doctype_meta = frappe.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = frappe.get_doc("DocType", "Test Blog Post")

		# remove last one
		doc.fields = doc.fields[:-1]
		self.assertRaises(frappe.CannotChangeConstantError, doc.save)
		frappe.clear_cache(doctype="DocType")

	def test_set_only_once_child_table_row_value(self):
		doctype_meta = frappe.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = frappe.get_doc("DocType", "Test Blog Post")
		# change one property from the child table
		doc.fields[-3].fieldtype = "Check"
		self.assertRaises(frappe.CannotChangeConstantError, doc.save)
		frappe.clear_cache(doctype="DocType")

	def test_set_only_once_child_table_okay(self):
		doctype_meta = frappe.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = frappe.get_doc("DocType", "Test Blog Post")

		doc.load_doc_before_save()
		self.assertFalse(doc.validate_set_only_once())
		frappe.clear_cache(doctype="DocType")

	def test_user_permission_doctypes(self):
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")
		add_user_permission("Test Blogger", "_Test Blogger 1", "test2@example.com")

		frappe.set_user("test2@example.com")

		frappe.clear_cache(doctype="Test Blog Post")

		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertFalse(doc.has_permission("read"))

		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post 2")
		self.assertTrue(doc.has_permission("read"))

		frappe.clear_cache(doctype="Test Blog Post")

	def if_owner_setup(self):
		update("Test Blog Post", "Blogger", 0, "if_owner", 1)

		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")
		add_user_permission("Test Blogger", "_Test Blogger 1", "test2@example.com")

		frappe.clear_cache(doctype="Test Blog Post")

	def test_insert_if_owner_with_user_permissions(self):
		"""If `If Owner` is checked for a Role, check if that document
		is allowed to be read, updated, submitted, etc. except be created,
		even if the document is restricted based on User Permissions."""
		frappe.delete_doc("Test Blog Post", "-test-blog-post-title")

		self.if_owner_setup()

		frappe.set_user("test2@example.com")

		doc = frappe.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category",
				"blogger": "_Test Blogger 1",
				"title": "_Test Blog Post Title",
				"content": "_Test Blog Post Content",
			}
		)

		self.assertRaises(frappe.PermissionError, doc.insert)

		frappe.set_user("test1@example.com")
		add_user_permission("Test Blog Category", "_Test Blog Category", "test2@example.com")

		frappe.set_user("test2@example.com")
		doc.insert()

		frappe.set_user("Administrator")
		remove_user_permission("Test Blog Category", "_Test Blog Category", "test2@example.com")
		frappe.clear_cache()
		frappe.set_user("test2@example.com")
		doc = frappe.get_doc(doc.doctype, doc.name)

		self.assertTrue(doc.has_permission("read"))
		self.assertTrue(doc.has_permission("write"))
		self.assertFalse(doc.has_permission("create"))

		# delete created record
		frappe.set_user("Administrator")
		frappe.delete_doc("Test Blog Post", "_Test Blog Post Title")

	def test_ignore_user_permissions_if_missing(self):
		"""If there are no user permissions, then allow as per role"""

		add_user_permission("Test Blog Category", "_Test Blog Category", "test2@example.com")
		frappe.set_user("test2@example.com")

		doc = frappe.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category 2",
				"blogger": "_Test Blogger 1",
				"title": "_Test Blog Post Title",
				"content": "_Test Blog Post Content",
			}
		)

		self.assertFalse(doc.has_permission("write"))

		frappe.set_user("Administrator")
		remove_user_permission("Test Blog Category", "_Test Blog Category", "test2@example.com")

		frappe.set_user("test2@example.com")
		self.assertTrue(doc.has_permission("write"))

	def test_strict_user_permissions(self):
		"""If `Strict User Permissions` is checked in System Settings,
		show records even if User Permissions are missing for a linked
		doctype"""

		frappe.set_user("Administrator")
		frappe.db.delete("Contact")
		frappe.db.delete("Contact Email")
		frappe.db.delete("Contact Phone")

		reset("Salutation")
		reset("Contact")

		make_test_records_for_doctype("Contact", force=True)

		add_user_permission("Salutation", "Mr", "test3@example.com")
		self.set_strict_user_permissions(0)

		allowed_contact = frappe.get_doc("Contact", "_Test Contact For _Test Customer")
		other_contact = frappe.get_doc("Contact", "_Test Contact For _Test Supplier")

		frappe.set_user("test3@example.com")
		self.assertTrue(allowed_contact.has_permission("read"))
		self.assertTrue(other_contact.has_permission("read"))
		self.assertEqual(len(frappe.get_list("Contact")), 2)

		frappe.set_user("Administrator")
		self.set_strict_user_permissions(1)

		frappe.set_user("test3@example.com")
		self.assertTrue(allowed_contact.has_permission("read"))
		self.assertFalse(other_contact.has_permission("read"))
		self.assertTrue(len(frappe.get_list("Contact")), 1)

		# This is a temporary WIP doc that user is using run_doc_method on
		local_doc = frappe.copy_doc(other_contact)
		self.assertTrue(local_doc.has_permission("read"))

		frappe.set_user("Administrator")
		self.set_strict_user_permissions(0)

		clear_user_permissions_for_doctype("Salutation")
		clear_user_permissions_for_doctype("Contact")

	def test_user_permission_is_not_applied_if_user_roles_does_not_have_permission(self):
		add_user_permission("Test Blog Post", "_Test Blog Post 1", "test3@example.com")
		frappe.set_user("test3@example.com")
		doc = frappe.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertFalse(doc.has_permission("read"))

		frappe.set_user("Administrator")
		user = frappe.get_doc("User", "test3@example.com")
		user.add_roles("Blogger")
		frappe.set_user("test3@example.com")
		self.assertTrue(doc.has_permission("read"))

		frappe.set_user("Administrator")
		user.remove_roles("Blogger")

	def test_contextual_user_permission(self):
		# should be applicable for across all doctypes
		add_user_permission("Test Blogger", "_Test Blogger", "test2@example.com")
		# should be applicable only while accessing Blog Post
		add_user_permission(
			"Test Blogger", "_Test Blogger 1", "test2@example.com", applicable_for="Test Blog Post"
		)
		# should be applicable only while accessing User
		add_user_permission("Test Blogger", "_Test Blogger 2", "test2@example.com", applicable_for="User")

		posts = frappe.get_all("Test Blog Post", fields=["name", "blogger"])

		# Get all posts for admin
		self.assertEqual(len(posts), 4)

		frappe.set_user("test2@example.com")

		posts = frappe.get_list("Test Blog Post", fields=["name", "blogger"])

		# Should get only posts with allowed blogger via user permission
		# only '_Test Blogger', '_Test Blogger 1' are allowed in Blog Post
		self.assertEqual(len(posts), 3)

		for post in posts:
			self.assertIn(
				post.blogger,
				["_Test Blogger", "_Test Blogger 1"],
				f"A post from {post.blogger} is not expected.",
			)

	def test_if_owner_permission_overrides_properly(self):
		# check if user is not granted access if the user is not the owner of the doc
		# Blogger has only read access on the blog post unless he is the owner of the blog
		update("Test Blog Post", "Blogger", 0, "if_owner", 1)
		update("Test Blog Post", "Blogger", 0, "read", 1, 1)
		update("Test Blog Post", "Blogger", 0, "write", 1, 1)
		update("Test Blog Post", "Blogger", 0, "delete", 1, 1)

		# currently test2 user has not created any document
		# still he should be able to do get_list query which should
		# not raise permission error but simply return empty list
		frappe.set_user("test2@example.com")
		self.assertEqual(frappe.get_list("Test Blog Post"), [])

		frappe.set_user("Administrator")

		# creates a custom docperm with just read access
		# now any user can read any blog post (but other rights are limited to the blog post owner)
		add_permission("Test Blog Post", "Blogger")
		frappe.clear_cache(doctype="Test Blog Post")

		frappe.delete_doc("Test Blog Post", "_Test Blog Post Title")

		frappe.set_user("test1@example.com")

		doc = frappe.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category",
				"blogger": "_Test Blogger 1",
				"title": "_Test Blog Post Title",
				"content": "_Test Blog Post Content",
			}
		)

		doc.insert()

		frappe.set_user("test2@example.com")
		doc = frappe.get_doc(doc.doctype, doc.name)

		self.assertTrue(doc.has_permission("read"))
		self.assertFalse(doc.has_permission("write"))
		self.assertFalse(doc.has_permission("delete"))

		# check if owner of the doc has the access that is available only for the owner of the doc
		frappe.set_user("test1@example.com")
		doc = frappe.get_doc(doc.doctype, doc.name)

		self.assertTrue(doc.has_permission("read"))
		self.assertTrue(doc.has_permission("write"))
		self.assertTrue(doc.has_permission("delete"))

		# delete the created doc
		frappe.delete_doc("Test Blog Post", "_Test Blog Post Title")

	def test_if_owner_permission_on_getdoc(self):
		update("Test Blog Post", "Blogger", 0, "if_owner", 1)
		update("Test Blog Post", "Blogger", 0, "read", 1)
		update("Test Blog Post", "Blogger", 0, "write", 1)
		update("Test Blog Post", "Blogger", 0, "delete", 1)
		frappe.clear_cache(doctype="Test Blog Post")

		frappe.set_user("test1@example.com")

		doc = frappe.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category",
				"blogger": "_Test Blogger 1",
				"title": "_Test Blog Post Title New",
				"content": "_Test Blog Post Content",
			}
		)

		doc.insert()

		getdoc("Test Blog Post", doc.name)
		doclist = [d.name for d in frappe.response.docs]
		self.assertTrue(doc.name in doclist)

		frappe.set_user("test2@example.com")
		self.assertRaises(frappe.PermissionError, getdoc, "Test Blog Post", doc.name)

	def test_if_owner_permission_on_get_list(self):
		doc = frappe.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category",
				"blogger": "_Test Blogger 1",
				"title": "_Test If Owner Permissions on Get List",
				"content": "_Test Blog Post Content",
			}
		)

		doc.insert(ignore_if_duplicate=True)

		update("Test Blog Post", "Blogger", 0, "if_owner", 1)
		update("Test Blog Post", "Blogger", 0, "read", 1)
		user = frappe.get_doc("User", "test2@example.com")
		user.add_roles("Website Manager")
		frappe.clear_cache(doctype="Test Blog Post")

		frappe.set_user("test2@example.com")
		self.assertIn(doc.name, frappe.get_list("Test Blog Post", pluck="name"))

		# Become system manager to remove role
		frappe.set_user("test1@example.com")
		user.remove_roles("Website Manager")
		frappe.clear_cache(doctype="Test Blog Post")

		frappe.set_user("test2@example.com")
		self.assertNotIn(doc.name, frappe.get_list("Test Blog Post", pluck="name"))

	def test_if_owner_permission_on_delete(self):
		update("Test Blog Post", "Blogger", 0, "if_owner", 1)
		update("Test Blog Post", "Blogger", 0, "read", 1, 1)
		update("Test Blog Post", "Blogger", 0, "write", 1, 1)
		update("Test Blog Post", "Blogger", 0, "delete", 1, 1)

		# Remove delete perm
		update("Test Blog Post", "Website Manager", 0, "delete", 0)

		frappe.clear_cache(doctype="Test Blog Post")

		with self.set_user("test2@example.com"):
			doc = frappe.get_doc(
				{
					"doctype": "Test Blog Post",
					"blog_category": "_Test Blog Category",
					"blogger": "_Test Blogger 1",
					"title": "_Test Blog Post Title New 1",
					"content": "_Test Blog Post Content",
				}
			)

			doc.insert()

			getdoc("Test Blog Post", doc.name)
			doclist = [d.name for d in frappe.response.docs]
			self.assertTrue(doc.name in doclist)

		with self.set_user("testperm@example.com"):
			# Website Manager able to read
			getdoc("Test Blog Post", doc.name)
			doclist = [d.name for d in frappe.response.docs]
			self.assertTrue(doc.name in doclist)

			# Website Manager should not be able to delete
			self.assertRaises(frappe.PermissionError, frappe.delete_doc, "Test Blog Post", doc.name)

		with self.set_user("test2@example.com"):
			frappe.delete_doc("Test Blog Post", "_Test Blog Post Title New 1")

		update("Test Blog Post", "Website Manager", 0, "delete", 1, 1)

	def test_clear_user_permissions(self):
		current_user = frappe.session.user
		frappe.set_user("Administrator")
		clear_user_permissions_for_doctype("Test Blog Category", "test2@example.com")
		clear_user_permissions_for_doctype("Test Blog Post", "test2@example.com")

		add_user_permission("Test Blog Post", "_Test Blog Post 1", "test2@example.com")
		add_user_permission("Test Blog Post", "_Test Blog Post 2", "test2@example.com")
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		deleted_user_permission_count = clear_user_permissions("test2@example.com", "Test Blog Post")

		self.assertEqual(deleted_user_permission_count, 2)

		blog_post_user_permission_count = frappe.db.count(
			"User Permission", filters={"user": "test2@example.com", "allow": "Test Blog Post"}
		)

		self.assertEqual(blog_post_user_permission_count, 0)

		blog_category_user_permission_count = frappe.db.count(
			"User Permission", filters={"user": "test2@example.com", "allow": "Test Blog Category"}
		)

		self.assertEqual(blog_category_user_permission_count, 1)

		# reset the user
		frappe.set_user(current_user)

	def test_child_permissions(self):
		frappe.set_user("test3@example.com")
		self.assertIsInstance(frappe.get_list("DefaultValue", parent_doctype="User", limit=1), list)

		# frappe.get_list
		self.assertRaises(frappe.PermissionError, frappe.get_list, "DefaultValue")
		self.assertRaises(frappe.PermissionError, frappe.get_list, "DefaultValue", parent_doctype="ToDo")
		self.assertRaises(
			frappe.PermissionError, frappe.get_list, "DefaultValue", parent_doctype="DefaultValue"
		)

		# frappe.get_doc
		user = frappe.get_doc("User", frappe.session.user)
		doc = user.append("defaults")
		doc.check_permission()

		# false due to missing parentfield
		doc = user.append("roles")
		doc.parentfield = None
		self.assertRaises(frappe.PermissionError, doc.check_permission)

		# false due to invalid parentfield
		doc = user.append("roles")
		doc.parentfield = "first_name"
		self.assertRaises(frappe.PermissionError, doc.check_permission)

		# false by permlevel
		doc = user.append("roles")
		self.assertRaises(frappe.PermissionError, doc.check_permission)

		# false by user permission
		user = frappe.get_doc("User", "Administrator")
		doc = user.append("defaults")
		self.assertRaises(frappe.PermissionError, doc.check_permission)

	def test_child_permission_error_reports_parent_doctype(self):
		with self.set_user("Administrator"):
			child_doctype = new_doctype(istable=1).insert().name
			parent_doctype = (
				new_doctype(
					fields=[
						{
							"label": "Rows",
							"fieldname": "rows",
							"fieldtype": "Table",
							"options": child_doctype,
							"permlevel": 1,
						}
					],
					permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
				)
				.insert()
				.name
			)
			parent = frappe.new_doc(parent_doctype)
			parent.append("rows", {})
			parent.insert()

		row = parent.rows[0]

		# no access to the parent doctype at all
		with self.set_user("test@example.com"):
			frappe.local.message_log = []
			self.assertRaises(frappe.PermissionError, row.check_permission, "delete")

			self.assertIn(parent_doctype, frappe.local.message_log[-1]["message"])
			self.assertIn(parent_doctype, frappe.flags.error_message)

		# access to the parent doctype, denied on the table's permlevel
		with self.set_user("test1@example.com"):
			self.assertRaises(frappe.PermissionError, row.check_permission, "delete")

			self.assertIn(parent_doctype, frappe.flags.error_message)
			self.assertIn(parent.name, frappe.flags.error_message)
			self.assertNotIn(child_doctype, frappe.flags.error_message)
			self.assertNotIn(row.name, frappe.flags.error_message)

	def test_select_user(self):
		"""If test3@example.com is restricted by a User Permission to see only
		users linked to a certain doctype (in this case: Gender "Female"), he
		should not be able to query other users (Gender "Male").
		"""
		# ensure required genders exist
		for gender in ("Male", "Female"):
			if frappe.db.exists("Gender", gender):
				continue

			frappe.get_doc({"doctype": "Gender", "gender": gender}).insert()

		# asssign gender to test users
		frappe.db.set_value("User", "test1@example.com", "gender", "Male")
		frappe.db.set_value("User", "test2@example.com", "gender", "Female")
		frappe.db.set_value("User", "test3@example.com", "gender", "Female")

		# restrict test3@example.com to see only female users
		add_user_permission("Gender", "Female", "test3@example.com")

		# become user test3@example.com and see what users he can query
		frappe.set_user("test3@example.com")
		users = frappe.get_list("User", pluck="name")

		self.assertNotIn("test1@example.com", users)
		self.assertIn("test2@example.com", users)
		self.assertIn("test3@example.com", users)

	def test_automatic_permissions(self):
		def assertHasRole(*roles: str | tuple[str, ...]):
			for role in roles:
				self.assertIn(role, frappe.get_roles())

		frappe.set_user("Administrator")
		assertHasRole(*AUTOMATIC_ROLES)

		frappe.set_user("Guest")
		assertHasRole(GUEST_ROLE)

		website_user = frappe.db.get_value(
			"User",
			{"user_type": "Website User", "enabled": 1, "name": ("not in", AUTOMATIC_ROLES)},
		)
		frappe.set_user(website_user)
		assertHasRole(GUEST_ROLE, ALL_USER_ROLE)

		system_user = frappe.db.get_value(
			"User",
			{"user_type": "System User", "enabled": 1, "name": ("not in", AUTOMATIC_ROLES)},
		)
		frappe.set_user(system_user)
		assertHasRole(GUEST_ROLE, ALL_USER_ROLE, SYSTEM_USER_ROLE)

	def test_get_doctypes_with_read(self):
		with self.set_user("Administrator"):
			doctype = new_doctype(permissions=[{"select": 1, "role": "_Test Role", "read": 0}]).insert().name

		with self.set_user("test@example.com"):
			self.assertNotIn(doctype, get_doctypes_with_read())

	def test_overrides_work_as_expected(self):
		"""custom docperms should completely override standard ones"""
		standard_role = "Desk User"
		custom_role = frappe.new_doc("Role", role_name=frappe.generate_hash()).insert().name
		with self.set_user("Administrator"):
			doctype = new_doctype(permissions=[{"role": standard_role, "read": 1}]).insert().name

		with self.set_user("test@example.com"):
			self.assertIn(doctype, get_doctypes_with_read())

		with self.set_user("Administrator"):
			# Allow perm to some other role and remove standard role
			add(doctype, custom_role, 0)
			remove(doctype, standard_role, 0)

		with self.set_user("test@example.com"):
			# No one has this role, so user shouldn't have permission.
			self.assertNotIn(doctype, get_doctypes_with_read())
