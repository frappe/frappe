# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re
from functools import partial

import frappe
from frappe.app import make_form_dict
from frappe.desk.search import get_names_for_mentions, search_link, search_widget
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response


class TestSearch(FrappeTestCase):
	def setUp(self):
		if self._testMethodName == "test_link_field_order":
			setup_test_link_field_order(self)
			self.addCleanup(teardown_test_link_field_order, self)

	def test_search_field_sanitizer(self):
		# pass
		search_link("DocType", "User", query=None, filters=None, page_length=20, searchfield="name")
		result = frappe.response["results"][0]
		self.assertTrue("User" in result["value"])

		# raise exception on injection
		for searchfield in (
			"1=1",
			"select * from tabSessions) --",
			"name or (select * from tabSessions)",
			"*",
			";",
			"select`sid`from`tabSessions`",
		):
			self.assertRaises(
				frappe.DataError,
				search_link,
				"DocType",
				"User",
				query=None,
				filters=None,
				page_length=20,
				searchfield=searchfield,
			)

	def test_only_enabled_in_mention(self):
		email = "test_disabled_user_in_mentions@example.com"
		frappe.delete_doc("User", email)
		if not frappe.db.exists("User", email):
			user = frappe.new_doc("User")
			user.update(
				{
					"email": email,
					"first_name": email.split("@", 1)[0],
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
		self.assertEqual(self.parent_doctype_name, result[0]["value"])

		# Check whether searching for parent also list out children
		self.assertEqual(len(result), len(self.child_doctypes_names) + 1)

	# Search for the word "pay", part of the word "pays" (country) in french.
	def test_link_search_in_foreign_language(self):
		try:
			frappe.local.lang = "fr"
			search_widget(doctype="DocType", txt="pay", page_length=20)
			output = frappe.response["values"]

			result = [["found" for x in y if x == "Country"] for y in output]
			self.assertTrue(["found"] in result)
		finally:
			frappe.local.lang = "en"

	def test_doctype_search_in_foreign_language(self):
		def do_search(txt: str):
			search_link(
				doctype="DocType",
				txt=txt,
				query="frappe.core.report.permitted_documents_for_user.permitted_documents_for_user.query_doctypes",
				filters={"user": "Administrator"},
				page_length=20,
				searchfield=None,
			)
			return frappe.response["results"]

		try:
			frappe.local.lang = "en"
			results = do_search("user")
			self.assertIn("User", [x["value"] for x in results])

			frappe.local.lang = "fr"
			results = do_search("utilisateur")
			self.assertIn("User", [x["value"] for x in results])

			frappe.local.lang = "de"
			results = do_search("nutzer")
			self.assertIn("User", [x["value"] for x in results])
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

	def test_reference_doctype(self):
		"""search query methods should get reference_doctype if they want"""
		results = test_search(
			doctype="User",
			txt="",
			filters=None,
			page_length=20,
			reference_doctype="ToDo",
			query="frappe.tests.test_search.query_with_reference_doctype",
		)
		self.assertListEqual(results, [])

	def test_search_relevance(self):
		search = partial(test_search, doctype="Language", filters=None, page_length=10)
		for row in search(txt="e"):
			self.assertTrue(row["value"].startswith("e"))

		for row in search(txt="es"):
			self.assertIn("es", row["value"])

		# Assume that "es" is used at least 10 times, it should now be first
		frappe.db.set_value("Language", "es", "idx", 10)
		self.assertEqual("es", search(txt="es")[0]["value"])


def test_search(*args, **kwargs):
	search_link(*args, **kwargs)
	return frappe.response["results"]


@frappe.validate_and_sanitize_search_inputs
def get_data(doctype, txt, searchfield, start, page_len, filters):
	return [doctype, txt, searchfield, start, page_len, filters]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def query_with_reference_doctype(
	doctype, txt, searchfield, start, page_len, filters, reference_doctype=None
):
	return []


def setup_test_link_field_order(TestCase):
	TestCase.tree_doctype_name = "Test Tree Order"
	TestCase.child_doctype_list = []
	TestCase.child_doctypes_names = ["USA", "India", "Russia", "China"]
	TestCase.parent_doctype_name = "All Territories"

	# Create Tree doctype
	if not frappe.db.exists("DocType", TestCase.tree_doctype_name):
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
	else:
		TestCase.tree_doc = frappe.get_doc("DocType", TestCase.tree_doctype_name)

	# Create root for the tree doctype
	if not frappe.db.exists(TestCase.tree_doctype_name, {"random": TestCase.parent_doctype_name}):
		frappe.get_doc(
			{"doctype": TestCase.tree_doctype_name, "random": TestCase.parent_doctype_name, "is_group": 1}
		).insert(ignore_if_duplicate=True)

	# Create children for the root
	for child_name in TestCase.child_doctypes_names:
		temp = frappe.get_doc(
			{
				"doctype": TestCase.tree_doctype_name,
				"random": child_name,
				"parent_test_tree_order": TestCase.parent_doctype_name,
			}
		).insert(ignore_if_duplicate=True)
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


class TestWebsiteSearch(FrappeTestCase):
	def get(self, path, user="Guest"):
		frappe.set_user(user)
		set_request(method="GET", path=path)
		make_form_dict(frappe.local.request)
		response = get_response()
		frappe.set_user("Administrator")
		return response

	def test_basic_search(self):

		no_search = self.get("/search")
		self.assertEqual(no_search.status_code, 200)

		response = self.get("/search?q=b")
		self.assertEqual(response.status_code, 200)
		self.assertIn("Search Results", response.get_data(as_text=True))
