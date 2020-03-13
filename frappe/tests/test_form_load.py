# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest
from frappe.desk.form.load import getdoctype, getdoc
from frappe.core.page.permission_manager.permission_manager import update, reset, add
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

test_dependencies = ['Blog Category', 'Blogger']

class TestFormLoad(unittest.TestCase):
	def test_load(self):
		getdoctype("DocType")
		meta = list(filter(lambda d: d.name=="DocType", frappe.response.docs))[0]
		self.assertEqual(meta.name, "DocType")
		self.assertTrue(meta.get("__js"))

		frappe.response.docs = []
		getdoctype("Event")
		meta = list(filter(lambda d: d.name=="Event", frappe.response.docs))[0]
		self.assertTrue(meta.get("__calendar_js"))

	def test_fieldlevel_permissions_in_load(self):
		blog = frappe.get_doc({
			"doctype": "Blog Post",
			"blog_category": "_Test Blog Category 1",
			"blog_intro": "Test Blog Intro",
			"blogger": "_Test Blogger 1",
			"content": "Test Blog Content",
			"title": "_Test Blog Post {}".format(frappe.utils.now()),
			"published": 0
		})

		blog.insert()

		user = frappe.get_doc('User', 'test@example.com')

		user_roles = frappe.get_roles()
		user.remove_roles(*user_roles)
		user.add_roles('Blogger')

		make_property_setter('Blog Post', 'published', 'permlevel', 1, 'Int')
		reset('Blog Post')
		add('Blog Post', 'Website Manager', 1)
		update('Blog Post', 'Website Manager', 1, 'write', 1)

		frappe.set_user(user.name)

		blog_doc = get_blog(blog.name)

		self.assertEqual(blog_doc.name, blog.name)
		# since published field has higher permlevel
		self.assertEqual(blog_doc.published, None)

		# this will be ignored because user does not
		# have write access on `published` field (or on permlevel 1 fields)
		blog_doc.published = 1
		blog_doc.save()
		# since published field has higher permlevel
		self.assertEqual(blog_doc.published, 0)

		frappe.set_user('Administrator')
		user.add_roles('Website Manager')
		frappe.set_user(user.name)

		doc = frappe.get_doc('Blog Post', blog.name)
		doc.published = 1
		doc.save()

		blog_doc = get_blog(blog.name)
		# now user should be allowed to read field with higher permlevel
		# (after adding Website Manager role)
		self.assertEqual(blog_doc.published, 1)

		frappe.set_user('Administrator')

		# reset user roles
		user.remove_roles('Blogger', 'Website Manager')
		user.add_roles(*user_roles)

	def test_fieldlevel_permissions_in_load_for_child_table(self):
		contact = frappe.new_doc('Contact')
		contact.first_name = '_Test Contact 1'
		contact.append('phone_nos', {'phone': '123456'})
		contact.insert()

		user = frappe.get_doc('User', 'test@example.com')

		user_roles = frappe.get_roles()
		user.remove_roles(*user_roles)
		user.add_roles('Accounts User')

		make_property_setter('Contact Phone', 'phone', 'permlevel', 1, 'Data')
		reset('Contact Phone')
		add('Contact', 'Sales User', 1)
		update('Contact', 'Sales User', 1, 'write', 1)

		frappe.set_user(user.name)

		contact = frappe.get_doc('Contact', '_Test Contact 1')

		contact.phone_nos[0].phone = '654321'
		contact.save()

		self.assertEqual(contact.phone_nos[0].phone, '123456')

		frappe.set_user('Administrator')
		user.add_roles('Sales User')
		frappe.set_user(user.name)

		contact.phone_nos[0].phone = '654321'
		contact.save()

		contact = frappe.get_doc('Contact', '_Test Contact 1')
		self.assertEqual(contact.phone_nos[0].phone, '654321')

		frappe.set_user('Administrator')

		# reset user roles
		user.remove_roles('Accounts User', 'Sales User')
		user.add_roles(*user_roles)


def get_blog(blog_name):
	frappe.response.docs = []
	getdoc('Blog Post', blog_name)
	doc = frappe.response.docs[0]
	return doc