# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re
from functools import partial
from typing import Any
from unittest.mock import patch

import frappe
from frappe.app import make_form_dict
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.search import awesomebar_search, get_names_for_mentions, search_link, search_widget
from frappe.permissions import add_user_permission
from frappe.tests.ui_test_helpers import whitelist_for_tests
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response


class TestSearch(FrappeTestCase):
	def setUp(self):
		if self._testMethodName == "test_link_field_order":
			setup_test_link_field_order(self)
			self.addCleanup(teardown_test_link_field_order, self)

	def test_search_field_sanitizer(self):
		results = search_link("DocType", "User", query=None, filters=None, page_length=20, searchfield="name")
		self.assertTrue("User" in results[0]["value"])

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

	def test_allowed_in_mentions_cache_invalidation(self):
		email = "test_allowed_in_mentions@example.com"
		frappe.delete_doc("User", email, ignore_missing=True)

		user = frappe.new_doc("User")
		user.update(
			{
				"email": email,
				"first_name": email.split("@", 1)[0],
				"enabled": True,
				"allowed_in_mentions": True,
			}
		)
		# saved when roles are added
		user.add_roles("System Manager")

		# Populate the users_for_mentions cache.
		names_for_mention = [user.get("id") for user in get_names_for_mentions("")]
		self.assertIn(email, names_for_mention)

		# Changing Allowed In Mentions should invalidate the cache.
		user.allowed_in_mentions = False
		user.save()

		names_for_mention = [user.get("id") for user in get_names_for_mentions("")]
		self.assertNotIn(email, names_for_mention)

		frappe.delete_doc("User", email)

	def test_link_field_order(self):
		# Making a request to the search_link with the tree doctype
		results = search_link(
			doctype=self.tree_doctype_name,
			txt="all",
			query=None,
			filters=None,
			page_length=20,
			searchfield=None,
		)

		# Check whether the result is sorted or not
		self.assertEqual(self.parent_doctype_name, results[0]["value"])

		# Check whether searching for parent also list out children
		self.assertEqual(len(results), len(self.child_doctypes_names) + 1)

	# Search for the word "pay", part of the word "pays" (country) in french.
	def test_link_search_in_foreign_language(self):
		try:
			frappe.local.lang = "fr"
			output = search_widget(doctype="DocType", txt="pay", page_length=20)

			result = [["found" for x in y if x == "Country"] for y in output]
			self.assertTrue(["found"] in result)
		finally:
			frappe.local.lang = "en"

	def test_doctype_search_in_foreign_language(self):
		def do_search(txt: str):
			return search_link(
				doctype="DocType",
				txt=txt,
				query="frappe.core.report.permitted_documents_for_user.permitted_documents_for_user.query_doctypes",
				filters={"user": "Administrator"},
				page_length=20,
				searchfield=None,
			)

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
			*("User", "Random", "select * from tabSessions) --", "1", "10", dict()),
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
		results = search_link("User", "user@random", searchfield="name")
		self.assertListEqual(results, [])

	def test_reference_doctype(self):
		"""search query methods should get reference_doctype if they want"""
		results = search_link(
			doctype="User",
			txt="",
			filters=None,
			page_length=20,
			reference_doctype="ToDo",
			query="frappe.tests.test_search.query_with_reference_doctype",
		)
		self.assertListEqual(results, [])

	def test_search_relevance(self):
		search = partial(search_link, doctype="Language", filters=None, page_length=10)
		for row in search(txt="e"):
			self.assertTrue(row["value"].startswith("e"))

		for row in search(txt="es"):
			self.assertIn("es", row["value"])

		# Assume that "es" is used at least 10 times, it should now be first
		frappe.db.set_value("Language", "es", "idx", 10)
		self.assertEqual("es", search(txt="es")[0]["value"])

	def test_relevance_skipped_without_txt(self):
		"""`_relevance` is a constant when txt is empty, so it must not be selected or sorted on."""

		def search_and_capture(txt):
			captured = []
			orig_sql = frappe.db.__class__.sql

			def _capture(*args, **kwargs):
				result = orig_sql(*args, **kwargs)
				captured.append(str(args[0].last_query))
				return result

			with patch.object(frappe.db.__class__, "sql", _capture):
				values = search_widget(doctype="Language", txt=txt, page_length=5)

			return values, "\n".join(captured)

		empty, empty_sql = search_and_capture("")
		typed, typed_sql = search_and_capture("e")

		self.assertNotIn("_relevance", empty_sql)
		self.assertIn("_relevance", typed_sql)

		# the result shape must not change: a mismatched strip would drop a real column
		self.assertEqual(len(empty[0]), len(typed[0]))

	def test_empty_search_still_orders_by_idx(self):
		"""Dropping the constant relevance key must not change the order of an empty search."""
		frappe.db.set_value("Language", "es", {"enabled": 1, "idx": 500})

		# page_length=1 leaves the python relevance_sorter no second row to reorder
		self.assertEqual("es", search_link("Language", "", page_length=1)[0]["value"])

	def test_search_with_paren(self):
		search = partial(search_link, doctype="Language", filters=None, page_length=10)
		result = search(txt="(txt)")
		self.assertEqual(result, [])

	def test_search_link_with_ignore_user_permissions(self):
		if frappe.db.exists("DocType", "Test Search Linked"):
			frappe.delete_doc("DocType", "Test Search Linked", force=True)

		new_doctype(
			name="Test Search Linked",
			fields=[{"label": "Title", "fieldname": "title", "fieldtype": "Data"}],
			permissions=[{"role": "System Manager", "read": 1, "write": 1}],
			search_fields="title",
		).insert()
		self.addCleanup(lambda: frappe.delete_doc("DocType", "Test Search Linked", force=True))

		allowed_doc = frappe.get_doc({"doctype": "Test Search Linked", "title": "Allowed Document"}).insert()
		restricted_doc = frappe.get_doc(
			{"doctype": "Test Search Linked", "title": "Restricted Document"}
		).insert()

		test_user = "test_search_user@example.com"
		if not frappe.db.exists("User", test_user):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": test_user,
					"first_name": "Test Search User",
					"user_type": "System User",
				}
			).insert(ignore_permissions=True)
			user.add_roles("System Manager")
			self.addCleanup(lambda: frappe.delete_doc("User", test_user, force=True))

		add_user_permission("Test Search Linked", allowed_doc.name, test_user)
		self.addCleanup(
			lambda: frappe.db.delete("User Permission", {"user": test_user, "allow": "Test Search Linked"})
		)

		frappe.set_user(test_user)
		self.addCleanup(lambda: frappe.set_user("Administrator"))

		# a custom query runs its own frappe.get_list, the flag should still apply
		results_from_custom_query = search_link(
			doctype="Test Search Linked",
			txt="Document",
			query="frappe.tests.test_search.query_by_title",
			ignore_user_permissions=True,
		)
		result_values = [r["value"] for r in results_from_custom_query]
		self.assertIn(allowed_doc.name, result_values)
		self.assertIn(restricted_doc.name, result_values)

		# and should not outlive the search call
		self.assertEqual([d.name for d in frappe.get_list("Test Search Linked")], [allowed_doc.name])

	def test_awesomebar_search_hook(self):
		real_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "awesomebar_search":
				return [
					"frappe.tests.test_search._awesomebar_help",
					"frappe.tests.test_search._awesomebar_broken",
					"frappe.tests.test_search._awesomebar_bad_items",
				]
			return real_get_hooks(hook, *args, **kwargs)

		with patch.object(frappe, "get_hooks", side_effect=get_hooks):
			self.assertEqual(awesomebar_search(""), [])
			self.assertEqual(awesomebar_search("   "), [])

			results = awesomebar_search("help")
			self.assertEqual(
				results,
				[
					{
						"label": "Open Help",
						"value": "Open Help",
						"index": 50,
						"route": ["https://docs.example.com"],
						"description": "Docs",
					},
					{
						"label": "ToDo List",
						"value": "ToDo List",
						"index": 0,
						"route": ["List", "ToDo"],
					},
				],
			)

			http_results = awesomebar_search("intranet")
			self.assertEqual(
				http_results,
				[
					{
						"label": "Intranet",
						"value": "Intranet",
						"index": 40,
						"route": ["http://docs.local"],
					},
				],
			)

			inapp_results = awesomebar_search("inapp")
			self.assertEqual(
				inapp_results,
				[
					{
						"label": "Desk Docs",
						"value": "Desk Docs",
						"index": 30,
						"route": ["/desk/docs/some/page"],
					},
				],
			)

			self.assertEqual(awesomebar_search("unrelated"), [])


def _awesomebar_help(txt):
	query = txt.lower()
	if "help" in query:
		return [
			{
				"label": "Open Help",
				"description": "Docs",
				"route": "https://docs.example.com",
				"index": 50,
			}
		]
	if "intranet" in query:
		return [
			{
				"label": "Intranet",
				"route": "http://docs.local",
				"index": 40,
			}
		]
	if "inapp" in query:
		return [
			{
				"label": "Desk Docs",
				"route": "/desk/docs/some/page",
				"index": 30,
			}
		]
	return []


def _awesomebar_broken(txt):
	raise RuntimeError("boom")


def _awesomebar_bad_items(txt):
	if "help" not in txt.lower():
		return []
	return [
		"not a dict",
		{},
		{"label": "JS", "route": "javascript:alert(1)"},
		{"label": "Proto", "route": "//evil.com"},
		{"label": "ToDo List", "route": ["List", "ToDo"]},
	]


@frappe.validate_and_sanitize_search_inputs
def get_data(doctype, txt, searchfield, start, page_len, filters):
	return [doctype, txt, searchfield, start, page_len, filters]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def query_with_reference_doctype(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: str | list | dict[str, Any],
	reference_doctype: str | None = None,
):
	return []


@whitelist_for_tests
@frappe.validate_and_sanitize_search_inputs
def query_by_title(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: str | list | dict[str, Any],
):
	return frappe.get_list(doctype, filters={"title": ("like", f"%{txt}%")}, as_list=True)


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
