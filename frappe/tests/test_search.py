# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re
from contextlib import contextmanager
from functools import partial

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.search import get_names_for_mentions, search_link, search_widget
from frappe.permissions import add_user_permission
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import whitelist_for_tests


class TestSearch(IntegrationTestCase):
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

	def test_link_search_in_foreign_language(self):
		with custom_translation("fr", "Country", "Pays"), use_language("fr"):
			output = search_widget(doctype="DocType", txt="pay", page_length=20)
			results = [result[0] for result in output]
			self.assertIn(
				"Country", results, "Search results for 'pay' in French should include 'Country' ('Pays')"
			)

	def test_doctype_search_in_foreign_language(self):
		def do_search(txt: str):
			results = search_link(
				doctype="DocType",
				txt=txt,
				query="frappe.core.report.permitted_documents_for_user.permitted_documents_for_user.query_doctypes",
				filters={"user": "Administrator"},
				page_length=20,
				searchfield=None,
			)
			return [x["value"] for x in results]

		self.assertIn("User", do_search("user"))

		with custom_translation("fr", "User", "Utilisateur"), use_language("fr"):
			self.assertIn(
				"User",
				do_search("utilisateur"),
				"Search results for 'utilisateur' in French should include 'User' ('Utilisateur')",
			)

		with custom_translation("de", "User", "Nutzer"), use_language("de"):
			self.assertIn(
				"User",
				do_search("nutzer"),
				"Search results for 'nutzer' in German should include 'User' ('Nutzer')",
			)

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
		frappe.db.set_value("Language", {"name": ("like", "e%")}, "enabled", 1)

		search = partial(search_link, doctype="Language", filters=None, page_length=10)
		for row in search(txt="e"):
			self.assertTrue(row["value"].startswith("e"))

		for row in search(txt="es"):
			self.assertIn("es", row["value"])

		# Assume that "es" is used at least 10 times, it should now be first
		frappe.db.set_value("Language", "es", "idx", 10)
		self.assertEqual("es", search(txt="es")[0]["value"])

	def test_search_with_paren(self):
		search = partial(search_link, doctype="Language", filters=None, page_length=10)
		result = search(txt="(txt)")
		self.assertEqual(result, [])

	def test_search_link_with_ignore_user_permissions(self):
		"""Test that ignore_user_permissions works correctly in search_link
		when the link field has ignore_user_permissions enabled"""

		# Clean up any leftover doctypes from previous test runs
		for dt in ("Test Search Form", "Test Search Linked"):
			if frappe.db.exists("DocType", dt):
				frappe.delete_doc("DocType", dt, force=True)

		# Create a test doctype to link to
		new_doctype(
			name="Test Search Linked",
			fields=[{"label": "Title", "fieldname": "title", "fieldtype": "Data"}],
			permissions=[{"role": "System Manager", "read": 1, "write": 1}],
			search_fields="title",
		).insert()

		# Create a form doctype with a link field that has ignore_user_permissions
		new_doctype(
			name="Test Search Form",
			fields=[
				{
					"label": "Linked Doc",
					"fieldname": "linked_doc",
					"fieldtype": "Link",
					"options": "Test Search Linked",
					"ignore_user_permissions": 1,
				}
			],
			permissions=[{"role": "System Manager", "read": 1, "write": 1}],
		).insert()

		self.addCleanup(
			lambda: frappe.delete_doc("DocType", "Test Search Form", force=True, ignore_missing=True)
		)
		self.addCleanup(lambda: frappe.delete_doc("DocType", "Test Search Linked", force=True))

		# Create some test documents
		allowed_doc = frappe.get_doc({"doctype": "Test Search Linked", "title": "Allowed Document"}).insert()
		restricted_doc = frappe.get_doc(
			{"doctype": "Test Search Linked", "title": "Restricted Document"}
		).insert()
		self.addCleanup(lambda: frappe.delete_doc("Test Search Linked", allowed_doc.name, force=True))
		self.addCleanup(lambda: frappe.delete_doc("Test Search Linked", restricted_doc.name, force=True))

		# Create a test user with restricted permissions
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

		# Add user permission to restrict the user to only allowed_doc
		add_user_permission("Test Search Linked", allowed_doc.name, test_user)
		self.addCleanup(
			lambda: frappe.db.delete("User Permission", {"user": test_user, "allow": "Test Search Linked"})
		)

		frappe.set_user(test_user)
		self.addCleanup(lambda: frappe.set_user("Administrator"))

		# Without ignore_user_permissions, only allowed_doc should be returned
		results_without_ignore = search_link(
			doctype="Test Search Linked",
			txt="Document",
			ignore_user_permissions=False,
		)
		result_values = [r["value"] for r in results_without_ignore]
		self.assertIn(allowed_doc.name, result_values)
		self.assertNotIn(restricted_doc.name, result_values)

		# With ignore_user_permissions + reference_doctype + link_fieldname, both should be returned
		results_with_ignore = search_link(
			doctype="Test Search Linked",
			txt="Document",
			ignore_user_permissions=True,
			reference_doctype="Test Search Form",
			link_fieldname="linked_doc",
		)
		result_values = [r["value"] for r in results_with_ignore]
		self.assertIn(allowed_doc.name, result_values)
		self.assertIn(restricted_doc.name, result_values)

		# With ignore_user_permissions=True but WITHOUT reference_doctype/link_fieldname,
		# the flag should be silently ignored and user permissions should apply
		results_without_context = search_link(
			doctype="Test Search Linked",
			txt="Document",
			ignore_user_permissions=True,
			# reference_doctype and link_fieldname not provided
		)
		result_values = [r["value"] for r in results_without_context]
		self.assertIn(allowed_doc.name, result_values)
		self.assertNotIn(restricted_doc.name, result_values)

	def test_search_link_ignore_user_permissions_validation(self):
		"""Test that ignore_user_permissions is validated correctly"""

		# Clean up any leftover doctypes from previous test runs
		for dt in ("Test Search Form No Ignore", "Test Search Form Wrong Link", "Test Search Linked2"):
			if frappe.db.exists("DocType", dt):
				frappe.delete_doc("DocType", dt, force=True)

		# Create doctypes for testing
		new_doctype(
			name="Test Search Linked2",
			fields=[{"label": "Title", "fieldname": "title", "fieldtype": "Data"}],
		).insert()

		# Form with link field WITHOUT ignore_user_permissions
		new_doctype(
			name="Test Search Form No Ignore",
			fields=[
				{
					"label": "Linked Doc",
					"fieldname": "linked_doc",
					"fieldtype": "Link",
					"options": "Test Search Linked2",
					"ignore_user_permissions": 0,
				}
			],
		).insert()

		self.addCleanup(
			lambda: frappe.delete_doc(
				"DocType", "Test Search Form No Ignore", force=True, ignore_missing=True
			)
		)
		self.addCleanup(
			lambda: frappe.delete_doc(
				"DocType", "Test Search Form Wrong Link", force=True, ignore_missing=True
			)
		)
		self.addCleanup(
			lambda: frappe.delete_doc("DocType", "Test Search Linked2", force=True, ignore_missing=True)
		)

		# Should throw when field does not have ignore_user_permissions
		self.assertRaises(
			frappe.ValidationError,
			search_link,
			doctype="Test Search Linked2",
			txt="test",
			ignore_user_permissions=True,
			reference_doctype="Test Search Form No Ignore",
			link_fieldname="linked_doc",
		)

		# Should throw when field doesn't exist
		self.assertRaises(
			frappe.ValidationError,
			search_link,
			doctype="Test Search Linked2",
			txt="test",
			ignore_user_permissions=True,
			reference_doctype="Test Search Form No Ignore",
			link_fieldname="nonexistent_field",
		)

		# Should throw when doctype doesn't match
		new_doctype(
			name="Test Search Form Wrong Link",
			fields=[
				{
					"label": "Wrong Link",
					"fieldname": "wrong_link",
					"fieldtype": "Link",
					"options": "User",  # Different doctype
					"ignore_user_permissions": 1,
				}
			],
		).insert()
		self.addCleanup(lambda: frappe.delete_doc("DocType", "Test Search Form Wrong Link", force=True))

		self.assertRaises(
			frappe.ValidationError,
			search_link,
			doctype="Test Search Linked2",
			txt="test",
			ignore_user_permissions=True,
			reference_doctype="Test Search Form Wrong Link",
			link_fieldname="wrong_link",
		)


@frappe.validate_and_sanitize_search_inputs
def get_data(doctype, txt, searchfield, start, page_len, filters):
	return [doctype, txt, searchfield, start, page_len, filters]


@whitelist_for_tests()
@frappe.validate_and_sanitize_search_inputs
def query_with_reference_doctype(doctype, txt, searchfield, start, page_len, filters, reference_doctype=None):
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


@contextmanager
def custom_translation(language: str, source_text: str, translated_text: str):
	doc = frappe.new_doc("Translation")
	doc.language = language
	doc.source_text = source_text
	doc.translated_text = translated_text
	doc.save()

	try:
		yield
	finally:
		doc.delete()


@contextmanager
def use_language(language: str):
	original_lang = frappe.local.lang
	frappe.local.lang = language

	try:
		yield
	finally:
		frappe.local.lang = original_lang


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
