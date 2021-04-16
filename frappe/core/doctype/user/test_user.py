# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest, uuid

from frappe.model.delete_doc import delete_doc
from frappe.utils.data import today, add_to_date
from frappe import _dict
from frappe.utils import get_url
from frappe.core.doctype.user.user import get_total_users
from frappe.core.doctype.user.user import MaxUsersReachedError, test_password_strength
from frappe.core.doctype.user.user import extract_mentions
from frappe.frappeclient import FrappeClient

test_records = frappe.get_test_records('User')

class TestUser(unittest.TestCase):
	def tearDown(self):
		# disable password strength test
		frappe.db.set_value("System Settings", "System Settings", "enable_password_policy", 0)
		frappe.db.set_value("System Settings", "System Settings", "minimum_password_score", "")
		frappe.db.set_value("System Settings", "System Settings", "password_reset_limit", 3)
		frappe.set_user('Administrator')

	def test_user_type(self):
		new_user = frappe.get_doc(dict(doctype='User', email='test-for-type@example.com',
			first_name='Tester')).insert()
		self.assertEqual(new_user.user_type, 'Website User')

		# social login userid for frappe
		self.assertTrue(new_user.social_logins[0].userid)
		self.assertEqual(new_user.social_logins[0].provider, "frappe")

		# role with desk access
		new_user.add_roles('_Test Role 2')
		new_user.save()
		self.assertEqual(new_user.user_type, 'System User')

		# clear role
		new_user.roles = []
		new_user.save()
		self.assertEqual(new_user.user_type, 'Website User')

		# role without desk access
		new_user.add_roles('_Test Role 4')
		new_user.save()
		self.assertEqual(new_user.user_type, 'Website User')

		delete_contact(new_user.name)
		frappe.delete_doc('User', new_user.name)


	def test_delete(self):
		frappe.get_doc("User", "test@example.com").add_roles("_Test Role 2")
		self.assertRaises(frappe.LinkExistsError, delete_doc, "Role", "_Test Role 2")
		frappe.db.sql("""delete from `tabHas Role` where role='_Test Role 2'""")
		delete_doc("Role","_Test Role 2")

		if frappe.db.exists("User", "_test@example.com"):
			delete_contact("_test@example.com")
			delete_doc("User", "_test@example.com")

		user = frappe.copy_doc(test_records[1])
		user.email = "_test@example.com"
		user.insert()

		frappe.get_doc({"doctype": "ToDo", "description": "_Test"}).insert()

		delete_contact("_test@example.com")
		delete_doc("User", "_test@example.com")

		self.assertTrue(not frappe.db.sql("""select * from `tabToDo` where owner=%s""",
			("_test@example.com",)))

		from frappe.core.doctype.role.test_role import test_records as role_records
		frappe.copy_doc(role_records[1]).insert()

	def test_get_value(self):
		self.assertEqual(frappe.db.get_value("User", "test@example.com"), "test@example.com")
		self.assertEqual(frappe.db.get_value("User", {"email":"test@example.com"}), "test@example.com")
		self.assertEqual(frappe.db.get_value("User", {"email":"test@example.com"}, "email"), "test@example.com")
		self.assertEqual(frappe.db.get_value("User", {"email":"test@example.com"}, ["first_name", "email"]),
			("_Test", "test@example.com"))
		self.assertEqual(frappe.db.get_value("User",
			{"email":"test@example.com", "first_name": "_Test"},
			["first_name", "email"]),
				("_Test", "test@example.com"))

		test_user = frappe.db.sql("select * from tabUser where name='test@example.com'",
			as_dict=True)[0]
		self.assertEqual(frappe.db.get_value("User", {"email":"test@example.com"}, "*", as_dict=True),
			test_user)

		self.assertEqual(frappe.db.get_value("User", "xxxtest@example.com"), None)

		frappe.db.set_value("Website Settings", "Website Settings", "_test", "_test_val")
		self.assertEqual(frappe.db.get_value("Website Settings", None, "_test"), "_test_val")
		self.assertEqual(frappe.db.get_value("Website Settings", "Website Settings", "_test"), "_test_val")

	def test_high_permlevel_validations(self):
		user = frappe.get_meta("User")
		self.assertTrue("roles" in [d.fieldname for d in user.get_high_permlevel_fields()])

		me = frappe.get_doc("User", "testperm@example.com")
		me.remove_roles("System Manager")

		frappe.set_user("testperm@example.com")

		me = frappe.get_doc("User", "testperm@example.com")
		me.add_roles("System Manager")

		# system manager is not added (it is reset)
		self.assertFalse('System Manager' in [d.role for d in me.roles])

		frappe.set_user("Administrator")

		me = frappe.get_doc("User", "testperm@example.com")
		me.add_roles("System Manager")

		# system manager now added by Administrator
		self.assertTrue("System Manager" in [d.role for d in me.get("roles")])

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


	def test_delete_user(self):
		new_user = frappe.get_doc(dict(doctype='User', email='test-for-delete@example.com',
			first_name='Tester Delete User')).insert()
		self.assertEqual(new_user.user_type, 'Website User')

		# role with desk access
		new_user.add_roles('_Test Role 2')
		new_user.save()
		self.assertEqual(new_user.user_type, 'System User')

		comm = frappe.get_doc({
			"doctype":"Communication",
			"subject": "To check user able to delete even if linked with communication",
			"content": "To check user able to delete even if linked with communication",
			"sent_or_received": "Sent",
			"user": new_user.name
		})
		comm.insert(ignore_permissions=True)

		delete_contact(new_user.name)
		frappe.delete_doc('User', new_user.name)
		self.assertFalse(frappe.db.exists('User', new_user.name))

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

	def test_comment_mentions(self):
		comment = '''
			<span class="mention" data-id="test.comment@example.com" data-value="Test" data-denotation-char="@">
				<span><span class="ql-mention-denotation-char">@</span>Test</span>
			</span>
		'''
		self.assertEqual(extract_mentions(comment)[0], "test.comment@example.com")

		comment = '''
			<div>
				Testing comment,
				<span class="mention" data-id="test.comment@example.com" data-value="Test" data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Test</span>
				</span>
				please check
			</div>
		'''
		self.assertEqual(extract_mentions(comment)[0], "test.comment@example.com")
		comment = '''
			<div>
				Testing comment for
				<span class="mention" data-id="test_user@example.com" data-value="Test" data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Test</span>
				</span>
				and
				<span class="mention" data-id="test.again@example1.com" data-value="Test" data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Test</span>
				</span>
				please check
			</div>
		'''
		self.assertEqual(extract_mentions(comment)[0], "test_user@example.com")
		self.assertEqual(extract_mentions(comment)[1], "test.again@example1.com")

		doc = frappe.get_doc({
			'doctype': 'User Group',
			'name': 'Team',
			'user_group_members': [{
				'user': 'test@example.com'
			}, {
				'user': 'test1@example.com'
			}]
		})
		doc.insert(ignore_if_duplicate=True)

		comment = '''
			<div>
				Testing comment for
				<span class="mention" data-id="Team" data-value="Team" data-is-group="true" data-denotation-char="@">
					<span><span class="ql-mention-denotation-char">@</span>Team</span>
				</span>
				please check
			</div>
		'''
		self.assertListEqual(extract_mentions(comment), ['test@example.com', 'test1@example.com'])

	def test_rate_limiting_for_reset_password(self):
		# Allow only one reset request for a day
		frappe.db.set_value("System Settings", "System Settings", "password_reset_limit", 1)
		frappe.db.commit()

		url = get_url()
		data={'cmd': 'frappe.core.doctype.user.user.reset_password', 'user': 'test@test.com'}

		# Clear rate limit tracker to start fresh
		key = f"rl:{data['cmd']}:{data['user']}"
		frappe.cache().delete(key)

		c = FrappeClient(url)
		res1 = c.session.post(url, data=data, verify=c.verify, headers=c.headers)
		res2 = c.session.post(url, data=data, verify=c.verify, headers=c.headers)
		self.assertEqual(res1.status_code, 200)
		self.assertEqual(res2.status_code, 417)

	# def test_user_rollback(self):
	# 	"""
	#	FIXME: This is failing with PR #12693 as Rollback can't happen if notifications sent on user creation.
	#	Make sure that notifications disabled.
	# 	"""
	# 	frappe.db.commit()
	# 	frappe.db.begin()
	# 	user_id = str(uuid.uuid4())
	# 	email = f'{user_id}@example.com'
	# 	try:
	# 		frappe.flags.in_import = True  # disable throttling
	# 		frappe.get_doc(dict(
	# 			doctype='User',
	# 			email=email,
	# 			first_name=user_id,
	# 		)).insert()
	# 	finally:
	# 		frappe.flags.in_import = False

	# 	# Check user has been added
	# 	self.assertIsNotNone(frappe.db.get("User", {"email": email}))

	# 	# Check that rollback works
	# 	frappe.db.rollback()
	# 	self.assertIsNone(frappe.db.get("User", {"email": email}))

def delete_contact(user):
	frappe.db.sql("DELETE FROM `tabContact` WHERE `email_id`= %s", user)
	frappe.db.sql("DELETE FROM `tabContact Email` WHERE `email_id`= %s", user)
