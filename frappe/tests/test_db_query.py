# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest

from frappe.model.db_query import DatabaseQuery
from frappe.desk.reportview import get_filters_cond

from frappe.permissions import add_user_permission, clear_user_permissions_for_doctype

test_dependencies = ['User', 'Blog Post']

class TestReportview(unittest.TestCase):
	def test_basic(self):
		self.assertTrue({"name":"DocType"} in DatabaseQuery("DocType").execute(limit_page_length=None))

	def test_build_match_conditions(self):
		clear_user_permissions_for_doctype('Blog Post', 'test2@example.com')

		test2user = frappe.get_doc('User', 'test2@example.com')
		test2user.add_roles('Blogger')
		frappe.set_user('test2@example.com')

		# this will get match conditions for Blog Post
		build_match_conditions = DatabaseQuery('Blog Post').build_match_conditions

		# Before any user permission is applied
		# get as filters
		self.assertEqual(build_match_conditions(as_condition=False), [])
		# get as conditions
		self.assertEqual(build_match_conditions(as_condition=True), "")

		add_user_permission('Blog Post', '-test-blog-post', 'test2@example.com', True)
		add_user_permission('Blog Post', '-test-blog-post-1', 'test2@example.com', True)

		# After applying user permission
		# get as filters
		self.assertTrue({'Blog Post': ['-test-blog-post-1', '-test-blog-post']} in build_match_conditions(as_condition=False))
		# get as conditions
		self.assertEqual(build_match_conditions(as_condition=True),
			"""(((ifnull(`tabBlog Post`.`name`, '')='' or `tabBlog Post`.`name` in ('-test-blog-post-1', '-test-blog-post'))))""")

		frappe.set_user('Administrator')

	def test_fields(self):
		self.assertTrue({"name":"DocType", "issingle":0} \
			in DatabaseQuery("DocType").execute(fields=["name", "issingle"], limit_page_length=None))

	def test_filters_1(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters=[["DocType", "name", "like", "J%"]]))

	def test_filters_2(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters=[{"name": ["like", "J%"]}]))

	def test_filters_3(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters={"name": ["like", "J%"]}))

	def test_filters_4(self):
		self.assertTrue({"name":"DocField"} \
			in DatabaseQuery("DocType").execute(filters={"name": "DocField"}))

	def test_in_not_in_filters(self):
		self.assertFalse(DatabaseQuery("DocType").execute(filters={"name": ["in", None]}))
		self.assertTrue({"name":"DocType"} \
				in DatabaseQuery("DocType").execute(filters={"name": ["not in", None]}))

		for result in [{"name":"DocType"}, {"name":"DocField"}]:
			self.assertTrue(result
				in DatabaseQuery("DocType").execute(filters={"name": ["in", 'DocType,DocField']}))

		for result in [{"name":"DocType"}, {"name":"DocField"}]:
			self.assertFalse(result
				in DatabaseQuery("DocType").execute(filters={"name": ["not in", 'DocType,DocField']}))

	def test_or_filters(self):
		data = DatabaseQuery("DocField").execute(
				filters={"parent": "DocType"}, fields=["fieldname", "fieldtype"],
				or_filters=[{"fieldtype":"Table"}, {"fieldtype":"Select"}])

		self.assertTrue({"fieldtype":"Table", "fieldname":"fields"} in data)
		self.assertTrue({"fieldtype":"Select", "fieldname":"document_type"} in data)
		self.assertFalse({"fieldtype":"Check", "fieldname":"issingle"} in data)

	def test_between_filters(self):
		""" test case to check between filter for date fields """
		frappe.db.sql("delete from tabEvent")

		# create events to test the between operator filter
		todays_event = create_event()
		event1 = create_event(starts_on="2016-07-05 23:59:59")
		event2 = create_event(starts_on="2016-07-06 00:00:00")
		event3 = create_event(starts_on="2016-07-07 23:59:59")
		event4 = create_event(starts_on="2016-07-08 00:00:01")

		# if the values are not passed in filters then event should be filter as current datetime
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", None]}, fields=["name"])

		self.assertTrue({ "name": event1.name } not in data)

		# if both from and to_date values are passed
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", ["2016-07-06", "2016-07-07"]]},
			fields=["name"])

		self.assertTrue({ "name": event2.name } in data)
		self.assertTrue({ "name": event3.name } in data)
		self.assertTrue({ "name": event1.name } not in data)
		self.assertTrue({ "name": event4.name } not in data)

		# if only one value is passed in the filter
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", ["2016-07-07"]]},
			fields=["name"])

		self.assertTrue({ "name": event3.name } in data)
		self.assertTrue({ "name": event4.name } in data)
		self.assertTrue({ "name": todays_event.name } in data)
		self.assertTrue({ "name": event1.name } not in data)
		self.assertTrue({ "name": event2.name } not in data)

	def test_ignore_permissions_for_get_filters_cond(self):
		frappe.set_user('test2@example.com')
		self.assertRaises(frappe.PermissionError, get_filters_cond, 'DocType', dict(istable=1), [])
		self.assertTrue(get_filters_cond('DocType', dict(istable=1), [], ignore_permissions=True))
		frappe.set_user('Administrator')

	def test_query_fields_sanitizer(self):
		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
				fields=["name", "issingle, version()"], limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "issingle, IF(issingle=1, (select name from tabUser), count(name))"],
			limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "issingle, (select count(*) from tabSessions)"],
			limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "issingle, SELECT LOCATE('', `tabUser`.`user`) AS user;"],
			limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "issingle, IF(issingle=1, (SELECT name from tabUser), count(*))"],
			limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "issingle ''"],limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "issingle,'"],limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "select * from tabSessions"],limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "issingle from --"],limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "issingle from tabDocType order by 2 --"],limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["name", "1' UNION SELECT * FROM __Auth --"],limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
			fields=["@@version"], limit_start=0, limit_page_length=1)

		data = DatabaseQuery("DocType").execute(fields=["count(`name`) as count"],
			limit_start=0, limit_page_length=1)
		self.assertTrue('count' in data[0])

		data = DatabaseQuery("DocType").execute(fields=["name", "issingle", "locate('', name) as _relevance"],
			limit_start=0, limit_page_length=1)
		self.assertTrue('_relevance' in data[0])

		data = DatabaseQuery("DocType").execute(fields=["name", "issingle", "date(creation) as creation"],
			limit_start=0, limit_page_length=1)
		self.assertTrue('creation' in data[0])

		if frappe.db.db_type != 'postgres':
			# datediff function does not exist in postgres
			data = DatabaseQuery("DocType").execute(fields=["name", "issingle",
				"datediff(modified, creation) as date_diff"], limit_start=0, limit_page_length=1)
			self.assertTrue('date_diff' in data[0])

	def test_nested_permission(self):
		frappe.set_user('Administrator')
		create_nested_doctype()
		create_nested_doctype_records()
		clear_user_permissions_for_doctype('Nested DocType')

		# user permission for only one root folder
		add_user_permission('Nested DocType', 'Level 1 A', 'test2@example.com')

		from frappe.core.page.permission_manager.permission_manager import update
		# to avoid if_owner filter
		update('Nested DocType', 'All', 0, 'if_owner', 0)

		frappe.set_user('test2@example.com')
		data = DatabaseQuery('Nested DocType').execute()

		# children of root folder (for which we added user permission) should be accessible
		self.assertTrue({'name': 'Level 2 A'} in data)
		self.assertTrue({'name': 'Level 2 A'} in data)

		# other folders should not be accessible
		self.assertFalse({'name': 'Level 1 B'} in data)
		self.assertFalse({'name': 'Level 2 B'} in data)
		update('Nested DocType', 'All', 0, 'if_owner', 1)
		frappe.set_user('Administrator')

	def test_filter_sanitizer(self):
		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
				fields=["name"], filters={'istable,': 1}, limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
				fields=["name"], filters={'editable_grid,': 1}, or_filters={'istable,': 1},
				limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
				fields=["name"], filters={'editable_grid,': 1},
				or_filters=[['DocType', 'istable,', '=', 1]],
				limit_start=0, limit_page_length=1)

		self.assertRaises(frappe.DataError, DatabaseQuery("DocType").execute,
				fields=["name"], filters={'editable_grid,': 1},
				or_filters=[['DocType', 'istable', '=', 1], ['DocType', 'beta and 1=1', '=', 0]],
				limit_start=0, limit_page_length=1)

		out = DatabaseQuery("DocType").execute(fields=["name"],
				filters={'editable_grid': 1, 'module': 'Core'},
				or_filters=[['DocType', 'istable', '=', 1]], order_by='creation')
		self.assertTrue('DocField' in [d['name'] for d in out])

		out = DatabaseQuery("DocType").execute(fields=["name"],
				filters={'issingle': 1}, or_filters=[['DocType', 'module', '=', 'Core']],
				order_by='creation')
		self.assertTrue('Role Permission for Page and Report' in [d['name'] for d in out])

		out = DatabaseQuery("DocType").execute(fields=["name"],
				filters={'track_changes': 1, 'module': 'Core'},
				order_by='creation')
		self.assertTrue('File' in [d['name'] for d in out])

		out = DatabaseQuery("DocType").execute(fields=["name"],
				filters=[
					['DocType', 'ifnull(track_changes, 0)', '=', 0],
					['DocType', 'module', '=', 'Core']
				], order_by='creation')
		self.assertTrue('DefaultValue' in [d['name'] for d in out])

	def test_of_not_of_descendant_ancestors(self):
		frappe.set_user('Administrator')
		clear_user_permissions_for_doctype('Nested DocType')

		# in descendants filter
		data = frappe.get_all('Nested DocType', {'name': ('descendants of', 'Level 2 A')})
		self.assertTrue({"name": "Level 3 A"} in data)

		data = frappe.get_all('Nested DocType', {'name': ('descendants of', 'Level 1 A')})
		self.assertTrue({"name": "Level 3 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertFalse({"name": "Level 2 B"} in data)
		self.assertFalse({"name": "Level 1 B"} in data)
		self.assertFalse({"name": "Level 1 A"} in data)
		self.assertFalse({"name": "Root"} in data)

		# in ancestors of filter
		data = frappe.get_all('Nested DocType', {'name': ('ancestors of', 'Level 2 A')})
		self.assertFalse({"name": "Level 3 A"} in data)
		self.assertFalse({"name": "Level 2 A"} in data)
		self.assertFalse({"name": "Level 2 B"} in data)
		self.assertFalse({"name": "Level 1 B"} in data)
		self.assertTrue({"name": "Level 1 A"} in data)
		self.assertTrue({"name": "Root"} in data)

		data = frappe.get_all('Nested DocType', {'name': ('ancestors of', 'Level 1 A')})
		self.assertFalse({"name": "Level 3 A"} in data)
		self.assertFalse({"name": "Level 2 A"} in data)
		self.assertFalse({"name": "Level 2 B"} in data)
		self.assertFalse({"name": "Level 1 B"} in data)
		self.assertFalse({"name": "Level 1 A"} in data)
		self.assertTrue({"name": "Root"} in data)

		# not descendants filter
		data = frappe.get_all('Nested DocType', {'name': ('not descendants of', 'Level 2 A')})
		self.assertFalse({"name": "Level 3 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 B"} in data)
		self.assertTrue({"name": "Level 1 A"} in data)
		self.assertTrue({"name": "Root"} in data)

		data = frappe.get_all('Nested DocType', {'name': ('not descendants of', 'Level 1 A')})
		self.assertFalse({"name": "Level 3 A"} in data)
		self.assertFalse({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 B"} in data)
		self.assertTrue({"name": "Level 1 B"} in data)
		self.assertTrue({"name": "Level 1 A"} in data)
		self.assertTrue({"name": "Root"} in data)

		# not ancestors of filter
		data = frappe.get_all('Nested DocType', {'name': ('not ancestors of', 'Level 2 A')})
		self.assertTrue({"name": "Level 3 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 B"} in data)
		self.assertTrue({"name": "Level 1 B"} in data)
		self.assertTrue({"name": "Level 1 A"} not in data)
		self.assertTrue({"name": "Root"} not in data)

		data = frappe.get_all('Nested DocType', {'name': ('not ancestors of', 'Level 1 A')})
		self.assertTrue({"name": "Level 3 A"} in data)
		self.assertTrue({"name": "Level 2 A"} in data)
		self.assertTrue({"name": "Level 2 B"} in data)
		self.assertTrue({"name": "Level 1 B"} in data)
		self.assertTrue({"name": "Level 1 A"} in data)
		self.assertFalse({"name": "Root"} in data)

		data = frappe.get_all('Nested DocType', {'name': ('ancestors of', 'Root')})
		self.assertTrue(len(data) == 0)
		self.assertTrue(len(frappe.get_all('Nested DocType', {'name': ('not ancestors of', 'Root')})) == len(frappe.get_all('Nested DocType')))


	def test_is_set_is_not_set(self):
		res = DatabaseQuery('DocType').execute(filters={'autoname': ['is', 'not set']})
		self.assertTrue({'name': 'Integration Request'} in res)
		self.assertTrue({'name': 'User'} in res)
		self.assertFalse({'name': 'Blogger'} in res)

		res = DatabaseQuery('DocType').execute(filters={'autoname': ['is', 'set']})
		self.assertTrue({'name': 'DocField'} in res)
		self.assertTrue({'name': 'Prepared Report'} in res)
		self.assertFalse({'name': 'Property Setter'} in res)

	def test_set_field_tables(self):
		# Tests _in_standard_sql_methods method in test_set_field_tables
		# The following query will break if the above method is broken
		data = frappe.db.get_list("Web Form",
			filters=[['Web Form Field', 'reqd', '=', 1]],
			group_by='amount_field',
			fields=['count(*) as count', '`amount_field` as name'],
			order_by='count desc',
			limit=50,
		)

	def test_pluck_name(self):
		names = DatabaseQuery("DocType").execute(filters={"name": "DocType"}, pluck="name")
		self.assertEqual(names, ["DocType"])

	def test_pluck_any_field(self):
		owners = DatabaseQuery("DocType").execute(filters={"name": "DocType"}, pluck="owner")
		self.assertEqual(owners, ["Administrator"])

def create_event(subject="_Test Event", starts_on=None):
	""" create a test event """

	from frappe.utils import get_datetime

	event = frappe.get_doc({
		"doctype": "Event",
		"subject": subject,
		"event_type": "Public",
		"starts_on": get_datetime(starts_on),
	}).insert(ignore_permissions=True)

	return event

def create_nested_doctype():
	if frappe.db.exists('DocType', 'Nested DocType'):
		return

	frappe.get_doc({
		'doctype': 'DocType',
		'name': 'Nested DocType',
		'module': 'Custom',
		'is_tree': 1,
		'custom': 1,
		'autoname': 'Prompt',
		'fields': [
			{'label': 'Description', 'fieldname': 'description'}
		],
		'permissions': [
			{'role': 'Blogger'}
		]
	}).insert()

def create_nested_doctype_records():
	'''
	Create a structure like:
	- Root
		- Level 1 A
			- Level 2 A
				- Level 3 A
		- Level 1 B
			- Level 2 B
	'''
	records = [
		{'name': 'Root', 'is_group': 1},
		{'name': 'Level 1 A', 'parent_nested_doctype': 'Root', 'is_group': 1},
		{'name': 'Level 2 A', 'parent_nested_doctype': 'Level 1 A', 'is_group': 1},
		{'name': 'Level 3 A', 'parent_nested_doctype': 'Level 2 A'},
		{'name': 'Level 1 B', 'parent_nested_doctype': 'Root', 'is_group': 1},
		{'name': 'Level 2 B', 'parent_nested_doctype': 'Level 1 B'},
	]

	for r in records:
		d = frappe.new_doc('Nested DocType')
		d.update(r)
		d.insert(ignore_permissions=True, ignore_if_duplicate=True)
