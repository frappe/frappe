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

test_records = frappe.get_test_records('Blog Post')

test_dependencies = ["User", "Contact", "Salutation"]

class TestPermissions(unittest.TestCase):
	def setUp(self):
		frappe.clear_cache(doctype="Blog Post")

		if not frappe.flags.permission_user_setup_done:
			user = frappe.get_doc("User", "test1@example.com")
			user.add_roles("Website Manager")
			user.add_roles("System Manager")

			user = frappe.get_doc("User", "test2@example.com")
			user.add_roles("Blogger")

			user = frappe.get_doc("User", "test3@example.com")
			user.add_roles("Sales User")
			frappe.flags.permission_user_setup_done = True

		reset('Blogger')
		reset('Blog Post')

		frappe.db.sql('delete from `tabUser Permission`')

		frappe.set_user("test1@example.com")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("Blogger", "_Test Blogger 1", "user", None)

		clear_user_permissions_for_doctype("Blog Category")
		clear_user_permissions_for_doctype("Blog Post")
		clear_user_permissions_for_doctype("Blogger")

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
		add_user_permission("Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		names = [d.name for d in frappe.get_list("Blog Post", fields=["name", "blog_category"])]

		self.assertTrue("-test-blog-post-1" in names)
		self.assertFalse("-test-blog-post" in names)

	def test_default_values(self):
		add_user_permission("Blog Category", "_Test Blog Category 1", "test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.new_doc("Blog Post")
		self.assertEqual(doc.get("blog_category"), "_Test Blog Category 1")

	def test_user_link_match_doc(self):
		blogger = frappe.get_doc("Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()

		frappe.set_user("test2@example.com")

		post = frappe.get_doc("Blog Post", "-test-blog-post-2")
		self.assertTrue(post.has_permission("read"))

		post1 = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertFalse(post1.has_permission("read"))

	def test_user_link_match_report(self):
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

	def test_user_permissions_if_applied_on_doc_being_evaluated(self):
		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertTrue(doc.has_permission("read"))

		frappe.set_user("test1@example.com")
		add_user_permission("Blog Post", "-test-blog-post", "test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertFalse(doc.has_permission("read"))

		doc = frappe.get_doc("Blog Post", "-test-blog-post")
		self.assertTrue(doc.has_permission("read"))

	def test_set_only_once(self):
		blog_post = frappe.get_meta("Blog Post")
		doc = frappe.get_doc("Blog Post", "-test-blog-post-1")
		doc.db_set('title', 'Old')
		blog_post.get_field("title").set_only_once = 1
		doc.title = "New"
		self.assertRaises(frappe.CannotChangeConstantError, doc.save)
		blog_post.get_field("title").set_only_once = 0

	def test_set_only_once_child_table_rows(self):
		doctype_meta = frappe.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = frappe.get_doc("DocType", "Blog Post")

		# remove last one
		doc.fields = doc.fields[:-1]
		self.assertRaises(frappe.CannotChangeConstantError, doc.save)
		frappe.clear_cache(doctype='DocType')

	def test_set_only_once_child_table_row_value(self):
		doctype_meta = frappe.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = frappe.get_doc("DocType", "Blog Post")

		# change one property from the child table
		doc.fields[-1].fieldtype = 'HTML'
		self.assertRaises(frappe.CannotChangeConstantError, doc.save)
		frappe.clear_cache(doctype='DocType')

	def test_set_only_once_child_table_okay(self):
		doctype_meta = frappe.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = frappe.get_doc("DocType", "Blog Post")

		doc.load_doc_before_save()
		self.assertFalse(doc.validate_set_only_once())
		frappe.clear_cache(doctype='DocType')

	def test_user_permission_doctypes(self):
		add_user_permission("Blog Category", "_Test Blog Category 1",
			"test2@example.com")
		add_user_permission("Blogger", "_Test Blogger 1",
			"test2@example.com")

		frappe.set_user("test2@example.com")

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

		frappe.model.meta.clear_cache("Blog Post")

	def test_insert_if_owner_with_user_permissions(self):
		"""If `If Owner` is checked for a Role, check if that document
		is allowed to be read, updated, submitted, etc. except be created,
		even if the document is restricted based on User Permissions."""
		frappe.delete_doc('Blog Post', '-test-blog-post-title')

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

		frappe.set_user('test1@example.com')
		add_user_permission("Blog Category", "_Test Blog Category",
			"test2@example.com")

		frappe.set_user("test2@example.com")
		doc.insert()

		frappe.set_user("Administrator")
		remove_user_permission("Blog Category", "_Test Blog Category",
			"test2@example.com")

		frappe.set_user("test2@example.com")
		doc = frappe.get_doc(doc.doctype, doc.name)
		self.assertTrue(doc.has_permission("read"))
		self.assertTrue(doc.has_permission("write"))
		self.assertFalse(doc.has_permission("create"))

	def test_ignore_user_permissions_if_missing(self):
		"""If there are no user permissions, then allow as per role"""

		add_user_permission("Blog Category", "_Test Blog Category",
			"test2@example.com")
		frappe.set_user("test2@example.com")

		doc = frappe.get_doc({
			"doctype": "Blog Post",
			"blog_category": "_Test Blog Category 2",
			"blogger": "_Test Blogger 1",
			"title": "_Test Blog Post Title",
			"content": "_Test Blog Post Content"
		})

		self.assertFalse(doc.has_permission("write"))

		frappe.set_user("Administrator")
		remove_user_permission("Blog Category", "_Test Blog Category",
			"test2@example.com")

		frappe.set_user("test2@example.com")
		self.assertTrue(doc.has_permission('write'))

	def test_strict_user_permissions(self):
		"""If `Strict User Permissions` is checked in System Settings,
			show records even if User Permissions are missing for a linked
			doctype"""

		frappe.set_user('Administrator')
		frappe.db.sql('delete from tabContact')

		reset('Salutation')
		reset('Contact')

		make_test_records_for_doctype('Contact', force=True)

		add_user_permission("Salutation", "Mr", "test3@example.com")
		self.set_strict_user_permissions(0)

		allowed_contact = frappe.get_doc('Contact', '_Test Contact for _Test Customer')
		other_contact = frappe.get_doc('Contact', '_Test Contact for _Test Supplier')

		frappe.set_user("test3@example.com")
		self.assertTrue(allowed_contact.has_permission('read'))
		self.assertTrue(other_contact.has_permission('read'))
		self.assertEqual(len(frappe.get_list("Contact")), 2)

		frappe.set_user("Administrator")
		self.set_strict_user_permissions(1)

		frappe.set_user("test3@example.com")
		self.assertTrue(allowed_contact.has_permission('read'))
		self.assertFalse(other_contact.has_permission('read'))
		self.assertTrue(len(frappe.get_list("Contact")), 1)

		frappe.set_user("Administrator")
		self.set_strict_user_permissions(0)

		clear_user_permissions_for_doctype("Salutation")
		clear_user_permissions_for_doctype("Contact")

	def test_user_permissions_not_applied_if_user_can_edit_user_permissions(self):
		add_user_permission('Blogger', '_Test Blogger 1', 'test1@example.com')

		# test1@example.com has rights to create user permissions
		# so it should not matter if explicit user permissions are not set
		self.assertTrue(frappe.get_doc('Blogger', '_Test Blogger').has_permission('read'))

	def test_user_permission_is_not_applied_if_user_roles_does_not_have_permission(self):
		add_user_permission('Blog Post', '-test-blog-post-1', 'test3@example.com')
		frappe.set_user("test3@example.com")
		doc = frappe.get_doc("Blog Post", "-test-blog-post-1")
		self.assertFalse(doc.has_permission("read"))

		frappe.set_user("Administrator")
		user = frappe.get_doc("User", "test3@example.com")
		user.add_roles("Blogger")
		frappe.set_user("test3@example.com")
		self.assertTrue(doc.has_permission("read"))

		frappe.set_user("Administrator")
		user.remove_roles("Blogger")