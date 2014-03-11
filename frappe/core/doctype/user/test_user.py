# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe, unittest

from frappe.model.delete_doc import delete_doc, LinkExistsError

class TestUser(unittest.TestCase):
	def test_delete(self):
		self.assertRaises(LinkExistsError, delete_doc, "Role", "_Test Role 2")
		frappe.db.sql("""delete from tabUserRole where role='_Test Role 2'""")
		delete_doc("Role","_Test Role 2")
		
		user = frappe.bean(copy=test_records[1])
		user.doc.email = "_test@example.com"
		user.insert()
		
		frappe.bean({"doctype": "ToDo", "description": "_Test"}).insert()
		
		delete_doc("User", "_test@example.com")
		
		self.assertTrue(not frappe.db.sql("""select * from `tabToDo` where owner=%s""",
			("_test@example.com",)))
		
		from frappe.core.doctype.role.test_role import test_records as role_records
		frappe.bean(copy=role_records[1]).insert()
		
	def test_get_value(self):
		self.assertEquals(frappe.db.get_value("User", "test@example.com"), "test@example.com")
		self.assertEquals(frappe.db.get_value("User", {"email":"test@example.com"}), "test@example.com")
		self.assertEquals(frappe.db.get_value("User", {"email":"test@example.com"}, "email"), "test@example.com")
		self.assertEquals(frappe.db.get_value("User", {"email":"test@example.com"}, ["first_name", "email"]), 
			("_Test", "test@example.com"))
		self.assertEquals(frappe.db.get_value("User", 
			{"email":"test@example.com", "first_name": "_Test"}, 
			["first_name", "email"]), 
				("_Test", "test@example.com"))
				
		test_user = frappe.db.sql("select * from tabUser where name='test@example.com'", 
			as_dict=True)[0]
		self.assertEquals(frappe.db.get_value("User", {"email":"test@example.com"}, "*", as_dict=True), 
			test_user)

		self.assertEquals(frappe.db.get_value("User", "xxxtest@example.com"), None)
		
		frappe.db.set_value("Control Panel", "Control Panel", "_test", "_test_val")
		self.assertEquals(frappe.db.get_value("Control Panel", None, "_test"), "_test_val")
		self.assertEquals(frappe.db.get_value("Control Panel", "Control Panel", "_test"), "_test_val")
		
	def test_doclist(self):
		p_meta = frappe.get_doctype("User")
		
		self.assertEquals(len(p_meta.get({"doctype": "DocField", "parent": "User", "fieldname": "first_name"})), 1)
		self.assertEquals(len(p_meta.get({"doctype": "DocField", "parent": "User", "fieldname": "^first"})), 1)
		self.assertEquals(len(p_meta.get({"fieldname": ["!=", "first_name"]})), len(p_meta) - 1)
		self.assertEquals(len(p_meta.get({"fieldname": ["in", ["first_name", "last_name"]]})), 2)
		self.assertEquals(len(p_meta.get({"fieldname": ["not in", ["first_name", "last_name"]]})), len(p_meta) - 2)
		
		
test_records = [
	[
		{
			"doctype":"User",
			"email": "test@example.com",
			"first_name": "_Test",
			"new_password": "testpassword",
			"enabled": 1
		},
		{
			"doctype":"UserRole",
			"parentfield":"user_roles",
			"role": "_Test Role"
		},
		{
			"doctype":"UserRole",
			"parentfield":"user_roles",
			"role": "System Manager"
		}
	],
	[
		{
			"doctype":"User",
			"email": "test1@example.com",
			"first_name": "_Test1",
			"new_password": "testpassword"
		}
	],
	[
		{
			"doctype":"User",
			"email": "test2@example.com",
			"first_name": "_Test2",
			"new_password": "testpassword"
		}
	],
	[
		{
			"doctype":"User",
			"email": "testdelete@example.com",
			"first_name": "_Test",
			"new_password": "testpassword",
			"enabled": 1
		}, 
		{
			"doctype":"UserRole",
			"parentfield":"user_roles",
			"role": "_Test Role 2"
		},
		{
			"doctype":"UserRole",
			"parentfield":"user_roles",
			"role": "System Manager"
		}
	],
]