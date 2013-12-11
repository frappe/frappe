# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import webnotes, unittest

from webnotes.model.utils import delete_doc, LinkExistsError

class TestProfile(unittest.TestCase):
	def test_delete(self):
		self.assertRaises(LinkExistsError, delete_doc, "Role", "_Test Role 2")
		webnotes.conn.sql("""delete from tabUserRole where role='_Test Role 2'""")
		delete_doc("Role","_Test Role 2")
		
		profile = webnotes.bean(copy=test_records[1])
		profile.doc.email = "_test@example.com"
		profile.insert()
		
		webnotes.bean({"doctype": "ToDo", "description": "_Test"}).insert()
		
		delete_doc("Profile", "_test@example.com")
		
		self.assertTrue(not webnotes.conn.sql("""select * from `tabToDo` where owner=%s""",
			"_test@example.com"))
		
		webnotes.bean({"doctype": "Role", "role_name": "_Test Role 2"}).insert()
		
	def test_get_value(self):
		self.assertEquals(webnotes.conn.get_value("Profile", "test@example.com"), "test@example.com")
		self.assertEquals(webnotes.conn.get_value("Profile", {"email":"test@example.com"}), "test@example.com")
		self.assertEquals(webnotes.conn.get_value("Profile", {"email":"test@example.com"}, "email"), "test@example.com")
		self.assertEquals(webnotes.conn.get_value("Profile", {"email":"test@example.com"}, ["first_name", "email"]), 
			("_Test", "test@example.com"))
		self.assertEquals(webnotes.conn.get_value("Profile", 
			{"email":"test@example.com", "first_name": "_Test"}, 
			["first_name", "email"]), 
				("_Test", "test@example.com"))
				
		test_profile = webnotes.conn.sql("select * from tabProfile where name='test@example.com'", 
			as_dict=True)[0]
		self.assertEquals(webnotes.conn.get_value("Profile", {"email":"test@example.com"}, "*", as_dict=True), 
			test_profile)

		self.assertEquals(webnotes.conn.get_value("Profile", "xxxtest@example.com"), None)
		
		webnotes.conn.set_value("Control Panel", "Control Panel", "_test", "_test_val")
		self.assertEquals(webnotes.conn.get_value("Control Panel", None, "_test"), "_test_val")
		self.assertEquals(webnotes.conn.get_value("Control Panel", "Control Panel", "_test"), "_test_val")
		
	def test_doclist(self):
		p_meta = webnotes.get_doctype("Profile")
		
		self.assertEquals(len(p_meta.get({"doctype": "DocField", "parent": "Profile", "fieldname": "first_name"})), 1)
		self.assertEquals(len(p_meta.get({"doctype": "DocField", "parent": "Profile", "fieldname": "^first"})), 1)
		self.assertEquals(len(p_meta.get({"fieldname": ["!=", "first_name"]})), len(p_meta) - 1)
		self.assertEquals(len(p_meta.get({"fieldname": ["in", ["first_name", "last_name"]]})), 2)
		self.assertEquals(len(p_meta.get({"fieldname": ["not in", ["first_name", "last_name"]]})), len(p_meta) - 2)
		
		
test_records = [[{
		"doctype":"Profile",
		"email": "test@example.com",
		"first_name": "_Test",
		"new_password": "testpassword",
		"enabled": 1
	}, {
		"doctype":"UserRole",
		"parentfield":"user_roles",
		"role": "_Test Role"
	}, {
		"doctype":"UserRole",
		"parentfield":"user_roles",
		"role": "System Manager"
	}],
	[{
		"doctype":"Profile",
		"email": "test1@example.com",
		"first_name": "_Test1",
		"new_password": "testpassword"
	}],
	[{
		"doctype":"Profile",
		"email": "test2@example.com",
		"first_name": "_Test2",
		"new_password": "testpassword"
	}],
	[{
		"doctype":"Profile",
		"email": "testdelete@example.com",
		"first_name": "_Test",
		"new_password": "testpassword",
		"enabled": 1
	}, {
		"doctype":"UserRole",
		"parentfield":"user_roles",
		"role": "_Test Role 2"
	}, {
		"doctype":"UserRole",
		"parentfield":"user_roles",
		"role": "System Manager"
	}],
]