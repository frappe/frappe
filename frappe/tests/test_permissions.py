# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

"""Use blog post test to test user permissions logic"""

import frappe
import frappe.defaults
import unittest
import json
import frappe.model.meta
from frappe.permissions import (add_user_permission, remove_user_permission,
	clear_user_permissions_for_doctype, get_doc_permissions, add_permission,
	get_valid_perms)
from frappe.core.page.permission_manager.permission_manager import update, reset
from frappe.test_runner import make_test_records_for_doctype
from six import string_types

test_records = frappe.get_test_records('Blog Post')

test_dependencies = ["User", "Contact", "Salutation"]

class TestPermissions(unittest.TestCase):
	def setUp(self):
		frappe.clear_cache(doctype="Blog Post")
		frappe.clear_cache(doctype="Contact")

		user = frappe.get_doc("User", "test1@example.com")
		user.add_roles("Website Manager")
		user.add_roles("System Manager")

		user = frappe.get_doc("User", "test2@example.com")
		user.add_roles("Blogger")

		user = frappe.get_doc("User", "test3@example.com")
		user.add_roles("Sales User")

		reset('Blogger')
		reset('Blog Post')
		reset('Contact')
		reset('Salutation')

		frappe.db.sql('delete from `tabUser Permission`')

		self.set_ignore_user_permissions_if_missing(0)

		frappe.set_user("test1@example.com")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Blogger", "_Test Blogger 1", "user", None)

		clear_user_permissions_for_doctype("Blog Category")
		clear_user_permissions_for_doctype("Blog Post")
		clear_user_permissions_for_doctype("Blogger")
		clear_user_permissions_for_doctype("Contact")
		clear_user_permissions_for_doctype("Salutation")

		reset('Blogger')
		reset('Blog Post')
		reset('Contact')
		reset('Salutation')

		self.set_ignore_user_permissions_if_missing(0)

	@staticmethod
	def set_ignore_user_permissions_if_missing(ignore):
		ss = frappe.get_doc("System Settings")
		ss.ignore_user_permissions_if_missing = ignore
		ss.flags.ignore_mandatory = 1
		ss.save()

	@staticmethod
	def set_strict_user_permissions(ignore):
		ss = frappe.get_doc("System Settings")
		ss.apply_strict_user_permissions = ignore
		ss.flags.ignore_mandatory = 1
		ss.save()

	def test_basic_permission(self):
		post = frappe.get_doc("Blog Post", "-test-blog-post")
		self.assertTrue(post.has_permission("read"))

	def test_user_permissions_in_doc(self):
		self.set_user_permission_doctypes(["Blog Category"])

		add_user_permission("Blog Category", "_Test Blog Category 1",
			"test2@example.com")

		frappe.set_user("test2@example.com")

		post = frappe.get_doc("Blog Post", "-test-blog-post")
		self.assertFalse(post.has_permission("read"))
		self.assertFalse(get_doc_permissions(post).get("read"))

		post1 = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertTrue(post1.has_permission("read"))
		self.assertTrue(get_doc_permissions(post1).get("read"))

	def test_user_permissions_in_report(self):
		self.set_user_permission_doctypes(["Blog Category"])

		add_user_permission("Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		names = [d.name for d in frappe.get_list("Blog Post", fields=["name", "blog_category"])]

		self.assertTrue("-test-blog-post-1" in names)
		self.assertFalse("-test-blog-post" in names)

	def test_default_values(self):
		add_user_permission("Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.new_doc("Blog Post")
		self.assertEquals(doc.get("blog_category"), "_Test Blog Category 1")

	def test_user_link_match_doc(self):
		self.set_user_permission_doctypes(["Blogger"])

		blogger = frappe.get_doc("Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()

		frappe.set_user("test2@example.com")

		post = frappe.get_doc("Blog Post", "-test-blog-post-2")
		self.assertTrue(post.has_permission("read"))

		post1 = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertFalse(post1.has_permission("read"))

	def test_user_link_match_report(self):
		self.set_user_permission_doctypes(["Blogger"])

		blogger = frappe.get_doc("Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()

		frappe.set_user("test2@example.com")

		names = [d.name for d in frappe.get_list("Blog Post", fields=["name", "owner"])]
		self.assertTrue("-test-blog-post-2" in names)
		self.assertFalse("-test-blog-post-1" in names)

	def test_set_user_permissions(self):
		frappe.set_user("test1@example.com")
		add_user_permission("Blog Post", "-test-blog-post", "test2@example.com")

	def test_not_allowed_to_set_user_permissions(self):
		frappe.set_user("test2@example.com")

		# this user can't add user permissions
		self.assertRaises(frappe.PermissionError, add_user_permission,
			"Blog Post", "-test-blog-post", "test2@example.com")

	def test_read_if_explicit_user_permissions_are_set(self):
		self.set_user_permission_doctypes(["Blog Post"])

		self.test_set_user_permissions()

		frappe.set_user("test2@example.com")

		# user can only access permitted blog post
		doc = frappe.get_doc("Blog Post", "-test-blog-post")
		self.assertTrue(doc.has_permission("read"))

		# and not this one
		doc = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertFalse(doc.has_permission("read"))

	def test_not_allowed_to_remove_user_permissions(self):
		self.test_set_user_permissions()

		frappe.set_user("test2@example.com")

		# user cannot remove their own user permissions
		self.assertRaises(frappe.PermissionError, remove_user_permission,
			"Blog Post", "-test-blog-post", "test2@example.com")

	def test_user_permissions_based_on_blogger(self):
		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertTrue(doc.has_permission("read"))

		self.set_user_permission_doctypes(["Blog Post"])

		frappe.set_user("test1@example.com")
		add_user_permission("Blog Post", "-test-blog-post", "test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertFalse(doc.has_permission("read"))

		doc = frappe.get_doc("Blog Post", "-test-blog-post")
		self.assertTrue(doc.has_permission("read"))

	def test_set_only_once(self):
		blog_post = frappe.get_meta("Blog Post")
		blog_post.get_field("title").set_only_once = 1
		doc = frappe.get_doc("Blog Post", "-test-blog-post-1")
		doc.title = "New"
		self.assertRaises(frappe.CannotChangeConstantError, doc.save)
		blog_post.get_field("title").set_only_once = 0

	def test_user_permission_doctypes(self):
		add_user_permission("Blog Category", "_Test Blog Category 1",
			"test2@example.com")
		add_user_permission("Blogger", "_Test Blogger 1",
			"test2@example.com")

		frappe.set_user("test2@example.com")

		self.set_user_permission_doctypes(["Blogger"])

		frappe.model.meta.clear_cache("Blog Post")

		doc = frappe.get_doc("Blog Post", "-test-blog-post")
		self.assertFalse(doc.has_permission("read"))

		doc = frappe.get_doc("Blog Post", "-test-blog-post-2")
		self.assertTrue(doc.has_permission("read"))

		frappe.model.meta.clear_cache("Blog Post")

	def if_owner_setup(self):
		update('Blog Post', 'Blogger', 0, 'if_owner', 1)

		add_user_permission("Blog Category", "_Test Blog Category 1",
			"test2@example.com")
		add_user_permission("Blogger", "_Test Blogger 1",
			"test2@example.com")

		update('Blog Post', 'Blogger', 0, 'user_permission_doctypes', json.dumps(["Blog Category"]))

		frappe.model.meta.clear_cache("Blog Post")

	def set_user_permission_doctypes(self, user_permission_doctypes):
		set_user_permission_doctypes(["Blog Post"], role="Blogger",
			apply_user_permissions=1, user_permission_doctypes=user_permission_doctypes)

	def test_insert_if_owner_with_user_permissions(self):
		"""If `If Owner` is checked for a Role, check if that document is allowed to be read, updated, submitted, etc. except be created, even if the document is restricted based on User Permissions."""
		frappe.delete_doc('Blog Post', '-test-blog-post-title')

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
		add_user_permission("Blog Category", "_Test Blog Category",
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
		# add_user_permission("Blog Category", "_Test Blog Category",
		# 	"test2@example.com")
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

	def test_strict_user_permissions(self):
		"""If `Strict User Permissions` is checked in System Settings,
			show records even if User Permissions are missing for a linked
			doctype"""

		frappe.set_user("Administrator")
		frappe.db.sql('delete from tabContact')
		make_test_records_for_doctype('Contact', force=True)

		set_user_permission_doctypes("Contact", role="Sales User",
			apply_user_permissions=1, user_permission_doctypes=['Salutation'])
		set_user_permission_doctypes("Salutation", role="All",
			apply_user_permissions=1, user_permission_doctypes=['Salutation'])

		add_user_permission("Salutation", "Mr", "test3@example.com")
		self.set_strict_user_permissions(0)

		frappe.set_user("test3@example.com")
		self.assertEquals(len(frappe.get_list("Contact")), 2)

		frappe.set_user("Administrator")
		self.set_strict_user_permissions(1)

		frappe.set_user("test3@example.com")
		self.assertTrue(len(frappe.get_list("Contact")), 1)

		frappe.set_user("Administrator")
		self.set_strict_user_permissions(0)

	def test_automatic_apply_user_permissions(self):
		'''Test user permissions are automatically applied when a user permission
		is created'''
		# create a user
		frappe.get_doc(dict(doctype='User', email='test_user_perm@example.com',
			first_name='tester')).insert(ignore_if_duplicate=True)
		frappe.get_doc(dict(doctype='Role', role_name='Test Role User Perm')
			).insert(ignore_if_duplicate=True)

		# add a permission for event
		add_permission('DocType', 'Test Role User Perm')
		frappe.get_doc('User', 'test_user_perm@example.com').add_roles('Test Role User Perm')


		# add user permission
		add_user_permission('Module Def', 'Core', 'test_user_perm@example.com', True)

		# check if user permission is applied in the new role
		_perm = None
		for perm in get_valid_perms('DocType', 'test_user_perm@example.com'):
			if perm.role == 'Test Role User Perm':
				_perm = perm

		self.assertEqual(_perm.apply_user_permissions, 1)

		# restrict by module
		self.assertTrue('Module Def' in json.loads(_perm.user_permission_doctypes))


def set_user_permission_doctypes(doctypes, role, apply_user_permissions,
	user_permission_doctypes):
	user_permission_doctypes = None if not user_permission_doctypes else json.dumps(user_permission_doctypes)

	if isinstance(doctypes, string_types):
		doctypes = [doctypes]

	for doctype in doctypes:
		update(doctype, role, 0, 'apply_user_permissions', 1)
		update(doctype, role, 0, 'user_permission_doctypes',
			user_permission_doctypes)

		frappe.clear_cache(doctype=doctype)
