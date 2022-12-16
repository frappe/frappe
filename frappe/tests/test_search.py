# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import unittest

import frappe
from frappe.desk.search import get_names_for_mentions, search_link, search_widget


class TestSearch(unittest.TestCase):
	def setUp(self):
		if self._testMethodName == "test_link_field_order":
			setup_test_link_field_order(self)

	def tearDown(self):
		if self._testMethodName == "test_link_field_order":
			teardown_test_link_field_order(self)

	def test_search_field_sanitizer(self):
		# pass
		search_link("DocType", "User", query=None, filters=None, page_length=20, searchfield="name")
		result = frappe.response["results"][0]
		self.assertTrue("User" in result["value"])

		# raise exception on injection
		self.assertRaises(
			frappe.DataError,
			search_link,
			"DocType",
			"Customer",
			query=None,
			filters=None,
			page_length=20,
			searchfield="1=1",
		)

		self.assertRaises(
			frappe.DataError,
			search_link,
			"DocType",
			"Customer",
			query=None,
			filters=None,
			page_length=20,
			searchfield="select * from tabSessions) --",
		)

		self.assertRaises(
			frappe.DataError,
			search_link,
			"DocType",
			"Customer",
			query=None,
			filters=None,
			page_length=20,
			searchfield="name or (select * from tabSessions)",
		)

		self.assertRaises(
			frappe.DataError,
			search_link,
			"DocType",
			"Customer",
			query=None,
			filters=None,
			page_length=20,
			searchfield="*",
		)

		self.assertRaises(
			frappe.DataError,
			search_link,
			"DocType",
			"Customer",
			query=None,
			filters=None,
			page_length=20,
			searchfield=";",
		)

		self.assertRaises(
			frappe.DataError,
			search_link,
			"DocType",
			"Customer",
			query=None,
			filters=None,
			page_length=20,
			searchfield=";",
		)

	def test_only_enabled_in_mention(self):
		email = "test_disabled_user_in_mentions@example.com"
		frappe.delete_doc("User", email)
		if not frappe.db.exists("User", email):
			user = frappe.new_doc("User")
			user.update(
				{
					"email": email,
					"first_name": email.split("@")[0],
					"enabled": False,
					"allowed_in_mentions": True,
				}
			)
			# saved when roles are added
			user.add_roles(
				"System Manager",
			)

		names_for_mention = [user.get("id") for user in get_names_for_mentions("")]
		self.assertNotIn(email, names_for_mention)

	def test_link_field_order(self):
		# Making a request to the search_link with the tree doctype
		search_link(
			doctype=self.tree_doctype_name,
			txt="all",
			query=None,
			filters=None,
			page_length=20,
			searchfield=None,
		)
		result = frappe.response["results"]

		# Check whether the result is sorted or not
		self.assertEquals(self.parent_doctype_name, result[0]["value"])

		# Check whether searching for parent also list out children
		self.assertEquals(len(result), len(self.child_doctypes_names) + 1)

	# Search for the word "pay", part of the word "pays" (country) in french.
	def test_link_search_in_foreign_language(self):
		try:
			frappe.local.lang = "fr"
			frappe.local.lang_full_dict = None  # discard translation cache
			search_widget(doctype="DocType", txt="pay", page_length=20)
			output = frappe.response["values"]

			result = [["found" for x in y if x == "Country"] for y in output]
			self.assertTrue(["found"] in result)
		finally:
			frappe.local.lang = "en"

	def test_validate_and_sanitize_search_inputs(self):

		# should raise error if searchfield is injectable
		self.assertRaises(
			frappe.DataError,
			get_data,
			*("User", "Random", "select * from tabSessions) --", "1", "10", dict())
		)

		# page_len and start should be converted to int
		self.assertListEqual(
			get_data("User", "Random", "email", "name or (select * from tabSessions)", "10", dict()),
			["User", "Random", "email", 0, 10, {}],
		)
		self.assertListEqual(
			get_data("User", "Random", "email", page_len="2", start="10", filters=dict()),
			["User", "Random", "email", 10, 2, {}],
		)

		# DocType can be passed as None which should be accepted
		self.assertListEqual(
			get_data(None, "Random", "email", "2", "10", dict()), [None, "Random", "email", 2, 10, {}]
		)

		# return empty string if passed doctype is invalid
		self.assertListEqual(get_data("Random DocType", "Random", "email", "2", "10", dict()), [])

		# should not fail if function is called via frappe.call with extra arguments
		args = ("Random DocType", "Random", "email", "2", "10", dict())
		kwargs = {"as_dict": False}
		self.assertListEqual(frappe.call("frappe.tests.test_search.get_data", *args, **kwargs), [])

		# should not fail if query has @ symbol in it
		search_link("User", "user@random", searchfield="name")
		self.assertListEqual(frappe.response["results"], [])


@frappe.validate_and_sanitize_search_inputs
def get_data(doctype, txt, searchfield, start, page_len, filters):
	return [doctype, txt, searchfield, start, page_len, filters]


def setup_test_link_field_order(TestCase):
	TestCase.tree_doctype_name = "Test Tree Order"
	TestCase.child_doctype_list = []
	TestCase.child_doctypes_names = ["USA", "India", "Russia", "China"]
	TestCase.parent_doctype_name = "All Territories"

	# Create Tree doctype
	TestCase.tree_doc = frappe.get_doc(
		{
			"doctype": "DocType",
			"name": TestCase.tree_doctype_name,
			"module": "Custom",
			"custom": 1,
			"is_tree": 1,
			"autoname": "field:random",
			"fields": [{"fieldname": "random", "label": "Random", "fieldtype": "Data"}],
		}
	).insert()
	TestCase.tree_doc.search_fields = "parent_test_tree_order"
	TestCase.tree_doc.save()

	# Create root for the tree doctype
	frappe.get_doc(
		{"doctype": TestCase.tree_doctype_name, "random": TestCase.parent_doctype_name, "is_group": 1}
	).insert()

	# Create children for the root
	for child_name in TestCase.child_doctypes_names:
		temp = frappe.get_doc(
			{
				"doctype": TestCase.tree_doctype_name,
				"random": child_name,
				"parent_test_tree_order": TestCase.parent_doctype_name,
			}
		).insert()
		TestCase.child_doctype_list.append(temp)


def teardown_test_link_field_order(TestCase):
	# Deleting all the created doctype
	for child_doctype in TestCase.child_doctype_list:
		child_doctype.delete()

	frappe.delete_doc(
		TestCase.tree_doctype_name,
		TestCase.parent_doctype_name,
		ignore_permissions=True,
		force=True,
		for_reload=True,
	)

	TestCase.tree_doc.delete()
