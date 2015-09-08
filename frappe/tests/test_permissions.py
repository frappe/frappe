# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

"""Use blog post test to test user permissions logic"""

import frappe
import frappe.defaults
import unittest
import json
import frappe.model.meta
from frappe.core.page.user_permissions.user_permissions import add, remove, get_permissions
from frappe.permissions import clear_user_permissions_for_doctype, get_doc_permissions

test_records = frappe.get_test_records('Blog Post')

test_dependencies = ["User"]

class TestPermissions(unittest.TestCase):
	def setUp(self):
		frappe.clear_cache(doctype="Blog Post")

		user = frappe.get_doc("User", "test1@example.com")
		user.add_roles("Website Manager")

		user = frappe.get_doc("User", "test2@example.com")
		user.add_roles("Blogger")

		frappe.db.sql("""update `tabDocPerm` set if_owner=0
			where parent='Blog Post' and permlevel=0 and permlevel=0 and role='Blogger'""")

		self.set_ignore_user_permissions_if_missing(0)

		frappe.set_user("test1@example.com")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Blogger", "_Test Blogger 1", "user", None)

		clear_user_permissions_for_doctype("Blog Category")
		clear_user_permissions_for_doctype("Blog Post")
		clear_user_permissions_for_doctype("Blogger")

		frappe.db.sql("""update `tabDocPerm` set user_permission_doctypes=null, apply_user_permissions=0
			where parent='Blog Post' and permlevel=0 and apply_user_permissions=1
			and `read`=1""")

		frappe.db.sql("""update `tabDocPerm` set if_owner=0
			where parent='Blog Post' and permlevel=0 and permlevel=0 and role='Blogger'""")

		self.set_ignore_user_permissions_if_missing(0)

	def set_ignore_user_permissions_if_missing(self, ignore):
		ss = frappe.get_doc("System Settings")
		ss.ignore_user_permissions_if_missing = ignore
		ss.flags.ignore_mandatory = 1
		ss.save()

	def test_basic_permission(self):
		post = frappe.get_doc("Blog Post", "_test-blog-post")
		self.assertTrue(post.has_permission("read"))

	def test_user_permissions_in_doc(self):
		self.set_user_permission_doctypes(["Blog Category"])

		frappe.permissions.add_user_permission("Blog Category", "_Test Blog Category 1",
			"test2@example.com")

		frappe.set_user("test2@example.com")

		post = frappe.get_doc("Blog Post", "_test-blog-post")
		self.assertFalse(post.has_permission("read"))
		self.assertFalse(get_doc_permissions(post).get("read"))

		post1 = frappe.get_doc("Blog Post", "_test-blog-post-1")
		self.assertTrue(post1.has_permission("read"))
		self.assertTrue(get_doc_permissions(post1).get("read"))

	def test_user_permissions_in_report(self):
		self.set_user_permission_doctypes(["Blog Category"])

		frappe.permissions.add_user_permission("Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		names = [d.name for d in frappe.get_list("Blog Post", fields=["name", "blog_category"])]

		self.assertTrue("_test-blog-post-1" in names)
		self.assertFalse("_test-blog-post" in names)

	def test_default_values(self):
		frappe.permissions.add_user_permission("Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.new_doc("Blog Post")
		self.assertEquals(doc.get("blog_category"), "_Test Blog Category 1")

	def test_user_link_match_doc(self):
		self.set_user_permission_doctypes(["Blogger"])

		blogger = frappe.get_doc("Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()

		frappe.set_user("test2@example.com")

		post = frappe.get_doc("Blog Post", "_test-blog-post-2")
		self.assertTrue(post.has_permission("read"))

		post1 = frappe.get_doc("Blog Post", "_test-blog-post-1")
		self.assertFalse(post1.has_permission("read"))

	def test_user_link_match_report(self):
		self.set_user_permission_doctypes(["Blogger"])

		blogger = frappe.get_doc("Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()

		frappe.set_user("test2@example.com")

		names = [d.name for d in frappe.get_list("Blog Post", fields=["name", "owner"])]
		self.assertTrue("_test-blog-post-2" in names)
		self.assertFalse("_test-blog-post-1" in names)

	def test_set_user_permissions(self):
		frappe.set_user("test1@example.com")
		add("test2@example.com", "Blog Post", "_test-blog-post")

	def test_not_allowed_to_set_user_permissions(self):
		frappe.set_user("test2@example.com")

		# this user can't add user permissions
		self.assertRaises(frappe.PermissionError, add,
			"test2@example.com", "Blog Post", "_test-blog-post")

	def test_read_if_explicit_user_permissions_are_set(self):
		self.set_user_permission_doctypes(["Blog Post"])

		self.test_set_user_permissions()

		frappe.set_user("test2@example.com")

		# user can only access permitted blog post
		doc = frappe.get_doc("Blog Post", "_test-blog-post")
		self.assertTrue(doc.has_permission("read"))

		# and not this one
		doc = frappe.get_doc("Blog Post", "_test-blog-post-1")
		self.assertFalse(doc.has_permission("read"))

	def test_not_allowed_to_remove_user_permissions(self):
		self.test_set_user_permissions()
		defname = get_permissions("test2@example.com", "Blog Post", "_test-blog-post")[0].name

		frappe.set_user("test2@example.com")

		# user cannot remove their own user permissions
		self.assertRaises(frappe.PermissionError, remove,
			"test2@example.com", defname, "Blog Post", "_test-blog-post")

	def test_user_permissions_based_on_blogger(self):
		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Blog Post", "_test-blog-post-1")
		self.assertTrue(doc.has_permission("read"))

		self.set_user_permission_doctypes(["Blog Post"])

		frappe.set_user("test1@example.com")
		add("test2@example.com", "Blog Post", "_test-blog-post")

		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Blog Post", "_test-blog-post-1")
		self.assertFalse(doc.has_permission("read"))

		doc = frappe.get_doc("Blog Post", "_test-blog-post")
		self.assertTrue(doc.has_permission("read"))

	def test_set_only_once(self):
		blog_post = frappe.get_meta("Blog Post")
		blog_post.get_field("title").set_only_once = 1
		doc = frappe.get_doc("Blog Post", "_test-blog-post-1")
		doc.title = "New"
		self.assertRaises(frappe.CannotChangeConstantError, doc.save)
		blog_post.get_field("title").set_only_once = 0

	def test_user_permission_doctypes(self):
		frappe.permissions.add_user_permission("Blog Category", "_Test Blog Category 1",
			"test2@example.com")
		frappe.permissions.add_user_permission("Blogger", "_Test Blogger 1",
			"test2@example.com")

		frappe.set_user("test2@example.com")

		self.set_user_permission_doctypes(["Blogger"])

		frappe.model.meta.clear_cache("Blog Post")

		doc = frappe.get_doc("Blog Post", "_test-blog-post")
		self.assertFalse(doc.has_permission("read"))

		doc = frappe.get_doc("Blog Post", "_test-blog-post-2")
		self.assertTrue(doc.has_permission("read"))

		frappe.model.meta.clear_cache("Blog Post")

	def if_owner_setup(self):
		frappe.db.sql("""update `tabDocPerm` set if_owner=1
			where parent='Blog Post' and permlevel=0 and permlevel=0 and role='Blogger'""")

		frappe.permissions.add_user_permission("Blog Category", "_Test Blog Category 1",
			"test2@example.com")
		frappe.permissions.add_user_permission("Blogger", "_Test Blogger 1",
			"test2@example.com")

		frappe.db.sql("""update `tabDocPerm` set user_permission_doctypes=%s
			where parent='Blog Post' and permlevel=0 and apply_user_permissions=1
			and `read`=1""", json.dumps(["Blog Category"]))

		frappe.model.meta.clear_cache("Blog Post")

	def set_user_permission_doctypes(self, user_permission_doctypes):
		set_user_permission_doctypes(doctype="Blog Post", role="Blogger",
			apply_user_permissions=1, user_permission_doctypes=user_permission_doctypes)

	def test_insert_if_owner_with_user_permissions(self):
		"""If `If Owner` is checked for a Role, check if that document is allowed to be read, updated, submitted, etc. except be created, even if the document is restricted based on User Permissions."""
		self.set_user_permission_doctypes(["Blog Category"])
		self.if_owner_setup()

		frappe.set_user("test2@example.com")

		doc = frappe.get_doc({
			"doctype": "Blog Post",
			"blog_category": "_Test Blog Category",
			"blogger": "_Test Blogger 1",
			"title": "_Test Blog Post Title",
			"content": "_Test Blog Post Content"
		})

		self.assertRaises(frappe.PermissionError, doc.insert)

		frappe.set_user("Administrator")
		frappe.permissions.add_user_permission("Blog Category", "_Test Blog Category",
			"test2@example.com")

		frappe.set_user("test2@example.com")
		doc.insert()

		frappe.set_user("Administrator")
		frappe.permissions.remove_user_permission("Blog Category", "_Test Blog Category",
			"test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.get_doc(doc.doctype, doc.name)
		self.assertTrue(doc.has_permission("read"))
		self.assertTrue(doc.has_permission("write"))
		self.assertFalse(doc.has_permission("create"))

	def test_ignore_user_permissions_if_missing(self):
		"""If `Ignore User Permissions If Missing` is checked in System Settings, show records even if User Permissions are missing for a linked doctype"""
		self.set_user_permission_doctypes(['Blog Category', 'Blog Post', 'Blogger'])

		frappe.set_user("Administrator")
		frappe.permissions.add_user_permission("Blog Category", "_Test Blog Category",
			"test2@example.com")
		frappe.set_user("test2@example.com")

		doc = frappe.get_doc({
			"doctype": "Blog Post",
			"blog_category": "_Test Blog Category",
			"blogger": "_Test Blogger 1",
			"title": "_Test Blog Post Title",
			"content": "_Test Blog Post Content"
		})

		self.assertFalse(doc.has_permission("write"))

		frappe.set_user("Administrator")
		self.set_ignore_user_permissions_if_missing(1)

		frappe.set_user("test2@example.com")
		self.assertTrue(doc.has_permission("write"))

def set_user_permission_doctypes(doctype, role, apply_user_permissions, user_permission_doctypes):
	user_permission_doctypes = None if not user_permission_doctypes else json.dumps(user_permission_doctypes)
	frappe.db.sql("""update `tabDocPerm` set apply_user_permissions=%(apply_user_permissions)s,
		user_permission_doctypes=%(user_permission_doctypes)s
		where parent=%(doctype)s and permlevel=0
		and `read`=1 and role=%(role)s""", {
			"apply_user_permissions": apply_user_permissions,
			"user_permission_doctypes": user_permission_doctypes,
			"doctype": doctype,
			"role": role
		})

	frappe.clear_cache(doctype=doctype)
