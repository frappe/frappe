# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest
import requests

from frappe.model.delete_doc import delete_doc
from frappe.utils.data import today, add_to_date
from frappe import _dict
from frappe.limits import update_limits, clear_limit
from frappe.utils import get_url
from frappe.core.doctype.user.user import get_total_users
from frappe.core.doctype.user.user import MaxUsersReachedError, test_password_strength

test_records = frappe.get_test_records('User')

class TestUser(unittest.TestCase):
	def tearDown(self):
		# disable password strength test
		frappe.db.set_value("System Settings", "System Settings", "enable_password_policy", 0)
		frappe.db.set_value("System Settings", "System Settings", "minimum_password_score", "")

	def test_user_type(self):
		new_user = frappe.get_doc(dict(doctype='User', email='test-for-type@example.com',
			first_name='Tester')).insert()
		self.assertEquals(new_user.user_type, 'Website User')

		# role with desk access
		new_user.add_roles('_Test Role 2')
		new_user.save()
		self.assertEquals(new_user.user_type, 'System User')

		# clear role
		new_user.roles = []
		new_user.save()
		self.assertEquals(new_user.user_type, 'Website User')

		# role without desk access
		new_user.add_roles('_Test Role 4')
		new_user.save()
		self.assertEquals(new_user.user_type, 'Website User')

		frappe.delete_doc('User', new_user.name)


	def test_delete(self):
		frappe.get_doc("User", "test@example.com").add_roles("_Test Role 2")
		self.assertRaises(frappe.LinkExistsError, delete_doc, "Role", "_Test Role 2")
		frappe.db.sql("""delete from `tabHas Role` where role='_Test Role 2'""")
		delete_doc("Role","_Test Role 2")

		if frappe.db.exists("User", "_test@example.com"):
			delete_doc("User", "_test@example.com")

		user = frappe.copy_doc(test_records[1])
		user.email = "_test@example.com"
		user.insert()

		frappe.get_doc({"doctype": "ToDo", "description": "_Test"}).insert()

		delete_doc("User", "_test@example.com")

		self.assertTrue(not frappe.db.sql("""select * from `tabToDo` where owner=%s""",
			("_test@example.com",)))

		from frappe.core.doctype.role.test_role import test_records as role_records
		frappe.copy_doc(role_records[1]).insert()

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

		frappe.db.set_value("Website Settings", "Website Settings", "_test", "_test_val")
		self.assertEquals(frappe.db.get_value("Website Settings", None, "_test"), "_test_val")
		self.assertEquals(frappe.db.get_value("Website Settings", "Website Settings", "_test"), "_test_val")

	def test_high_permlevel_validations(self):
		user = frappe.get_meta("User")
		self.assertTrue("roles" in [d.fieldname for d in user.get_high_permlevel_fields()])

		me = frappe.get_doc("User", "testperm@example.com")
		me.remove_roles("System Manager")

		frappe.set_user("testperm@example.com")

		me = frappe.get_doc("User", "testperm@example.com")
		self.assertRaises(frappe.PermissionError, me.add_roles, "System Manager")

		frappe.set_user("Administrator")

		me = frappe.get_doc("User", "testperm@example.com")
		me.add_roles("System Manager")

		self.assertTrue("System Manager" in [d.role for d in me.get("roles")])

	def test_user_limit_for_site(self):
		update_limits({'users': get_total_users()})

		# reload site config
		from frappe import _dict
		frappe.local.conf = _dict(frappe.get_site_config())

		# Create a new user
		user = frappe.new_doc('User')
		user.email = 'test_max_users@example.com'
		user.first_name = 'Test_max_user'

		self.assertRaises(MaxUsersReachedError, user.add_roles, 'System Manager')

		if frappe.db.exists('User', 'test_max_users@example.com'):
			frappe.delete_doc('User', 'test_max_users@example.com')

		# Clear the user limit
		clear_limit('users')

	def test_user_limit_for_site_with_simultaneous_sessions(self):
		clear_limit('users')

		# make sure this user counts
		user = frappe.get_doc('User', 'test@example.com')
		user.add_roles('Website Manager')
		user.save()

		update_limits({'users': get_total_users()})

		user.simultaneous_sessions = user.simultaneous_sessions + 1

		self.assertRaises(MaxUsersReachedError, user.save)

		# Clear the user limit
		clear_limit('users')

	# def test_deny_multiple_sessions(self):
	#	from frappe.installer import update_site_config
	# 	clear_limit('users')
	#
	# 	# allow one session
	# 	user = frappe.get_doc('User', 'test@example.com')
	# 	user.simultaneous_sessions = 1
	# 	user.new_password = 'Eastern_43A1W'
	# 	user.save()
	#
	# 	def test_request(conn):
	# 		value = conn.get_value('User', 'first_name', {'name': 'test@example.com'})
	# 		self.assertTrue('first_name' in value)
	#
	# 	from frappe.frappeclient import FrappeClient
	# 	update_site_config('deny_multiple_sessions', 0)
	#
	# 	conn1 = FrappeClient(get_url(), "test@example.com", "Eastern_43A1W", verify=False)
	# 	test_request(conn1)
	#
	# 	conn2 = FrappeClient(get_url(), "test@example.com", "Eastern_43A1W", verify=False)
	# 	test_request(conn2)
	#
	# 	update_site_config('deny_multiple_sessions', 1)
	# 	conn3 = FrappeClient(get_url(), "test@example.com", "Eastern_43A1W", verify=False)
	# 	test_request(conn3)
	#
	# 	# first connection should fail
	# 	test_request(conn1)

	def test_site_expiry(self):
		user = frappe.get_doc('User', 'test@example.com')
		user.enabled = 1
		user.new_password = 'Eastern_43A1W'
		user.save()

		update_limits({'expiry': add_to_date(today(), days=-1), 'support_email': 'support@example.com'})
		frappe.local.conf = _dict(frappe.get_site_config())

		frappe.db.commit()

		res = requests.post(get_url(), params={'cmd': 'login', 'usr':
			'test@example.com', 'pwd': 'Eastern_43A1W', 'device': 'desktop'})

		# While site is expired status code returned is 417 Failed Expectation
		self.assertEqual(res.status_code, 417)

		clear_limit("expiry")
		frappe.local.conf = _dict(frappe.get_site_config())

	def test_delete_user(self):
		new_user = frappe.get_doc(dict(doctype='User', email='test-for-delete@example.com',
			first_name='Tester Delete User')).insert()
		self.assertEquals(new_user.user_type, 'Website User')

		# role with desk access
		new_user.add_roles('_Test Role 2')
		new_user.save()
		self.assertEquals(new_user.user_type, 'System User')

		comm = frappe.get_doc({
			"doctype":"Communication",
			"subject": "To check user able to delete even if linked with communication",
			"content": "To check user able to delete even if linked with communication",
			"sent_or_received": "Sent",
			"user": new_user.name
		})
		comm.insert(ignore_permissions=True)

		frappe.delete_doc('User', new_user.name)
		self.assertFalse(frappe.db.exists('User', new_user.name))

	def test_deactivate_additional_users(self):
		update_limits({'users': get_total_users()+1})

		if not frappe.db.exists("User", "test_deactivate_additional_users@example.com"):
			user = frappe.new_doc('User')
			user.email = 'test_deactivate_additional_users@example.com'
			user.first_name = 'Test Deactivate Additional Users'
			user.add_roles("System Manager")

		#update limits
		update_limits({"users": get_total_users()-1})
		self.assertEqual(frappe.db.get_value("User", "test_deactivate_additional_users@example.com", "enabled"), 0)

		if frappe.db.exists("User", "test_deactivate_additional_users@example.com"):
			frappe.delete_doc('User', 'test_deactivate_additional_users@example.com')

		# Clear the user limit
		clear_limit('users')

	def test_password_strength(self):
		# Test Password without Password Strenth Policy
		frappe.db.set_value("System Settings", "System Settings", "enable_password_policy", 0)

		# password policy is disabled, test_password_strength should be ignored
		result = test_password_strength("test_password")
		self.assertFalse(result.get("feedback", None))

		# Test Password with Password Strenth Policy Set
		frappe.db.set_value("System Settings", "System Settings", "enable_password_policy", 1)
		frappe.db.set_value("System Settings", "System Settings", "minimum_password_score", 2)

		# Score 1; should now fail
		result = test_password_strength("bee2ve")
		self.assertEqual(result['feedback']['password_policy_validation_passed'], False)

		# Score 4; should pass
		result = test_password_strength("Eastern_43A1W")
		self.assertEqual(result['feedback']['password_policy_validation_passed'], True)
