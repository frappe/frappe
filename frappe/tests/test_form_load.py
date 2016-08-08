# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest
from frappe.desk.form.load import getdoctype, getdoc

class TestFormLoad(unittest.TestCase):
	def test_load(self):
		getdoctype("DocType")
		meta = filter(lambda d: d.name=="DocType", frappe.response.docs)[0]
		self.assertEquals(meta.name, "DocType")
		self.assertTrue(meta.get("__js"))

		frappe.response.docs = []
		getdoctype("Event")
		meta = filter(lambda d: d.name=="Event", frappe.response.docs)[0]
		self.assertTrue(meta.get("__calendar_js"))

	def test_fieldlevel_permissions_in_load(self):
		user = frappe.get_doc('User', 'test@example.com')
		user.remove_roles('Website Manager')
		user.add_roles('Blogger')
		frappe.set_user(user.name)

		frappe.db.sql('update tabDocField set permlevel=1 where fieldname="published" and parent="Blog Post"')
		frappe.db.sql('update tabDocPerm set permlevel=1 where role="Website Manager" and parent="Blog Post"')
		frappe.clear_cache(doctype='Blog Post')

		blog = frappe.db.get_value('Blog Post', {'title': '_Test Blog Post'})

		getdoc('Blog Post', blog)

		checked = False

		for doc in frappe.response.docs:
			if doc.name == blog:
				self.assertEquals(doc.published, None)
				checked = True

		self.assertTrue(checked, True)

		frappe.db.sql('update tabDocField set permlevel=0 where fieldname="published" and parent="Blog Post"')
		frappe.db.sql('update tabDocPerm set permlevel=0 where role="Website Manager" and parent="Blog Post"')

		frappe.clear_cache(doctype='Blog Post')

		frappe.response.docs = []
		getdoc('Blog Post', blog)

		checked = False

		for doc in frappe.response.docs:
			if doc.name == blog:
				self.assertEquals(doc.published, 1)
				checked = True

		self.assertTrue(checked, True)

		frappe.set_user('Administrator')
