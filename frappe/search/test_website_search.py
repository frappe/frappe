# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.search.website_search import WebsiteSearch
from frappe.tests import IntegrationTestCase


class TestWebsiteSearch(IntegrationTestCase):
	def setUp(self):
		self.index = get_index()
		self.index.build()
		self.addCleanup(self.index.drop_index)

	def test_search_term(self):
		res = self.index.search("multilingual online encyclopedia")
		self.assertEqual(res[0].path, "site/wikipedia")

		res = self.index.search("Linux kernel")
		self.assertEqual(res[0].path, "os/linux")

		res = self.index.search("Enterprise Resource Planning")
		self.assertEqual(res[0].path, "sw/erpnext")

	def test_search_limit(self):
		res = self.index.search("CommonSearchTerm")
		self.assertEqual(len(res), 5)

		res = self.index.search("CommonSearchTerm", limit=3)
		self.assertEqual(len(res), 3)

		res = self.index.search("CommonSearchTerm", limit=20)
		self.assertEqual(len(res), 5)

	def test_search_scope(self):
		# Search outside scope
		res = self.index.search("multilingual online encyclopedia", scope="os")
		self.assertEqual(len(res), 0)

		# Search inside scope
		res = self.index.search("CommonSearchTerm", scope="os")
		paths = {r.path for r in res}
		self.assertEqual(paths, {"os/linux", "os/gnu"})

	def test_remove_document_from_index(self):
		self.index.remove_document_from_index("os/gnu")
		res = self.index.search("GNU")
		self.assertEqual(len(res), 0)

	def test_update_index(self):
		# Update existing route
		self.index.update_index({"title": "ERPNext", "content": "AwesomeERPNext", "path": "sw/erpnext"})

		res = self.index.search("AwesomeERPNext")
		self.assertEqual(res[0].path, "sw/erpnext")

		# Index a brand new route
		self.index.update_index(
			{"title": "Frappe Books", "content": "DesktopAccounting", "path": "sw/frappebooks"}
		)

		res = self.index.search("DesktopAccounting")
		self.assertEqual(res[0].path, "sw/frappebooks")

	def test_search_highlights(self):
		res = self.index.search("Linux kernel")
		self.assertIn("<mark>", res[0].content_highlights)
		# Plain title must not carry highlight markup
		self.assertNotIn("<mark>", res[0].title)


class TestWrapper(WebsiteSearch):
	"""Feeds canned route documents so tests don't render real web routes."""

	def get_items_to_index(self):
		return [frappe._dict(doc) for doc in get_documents()]

	def get_document_to_index(self, route):
		for doc in get_documents():
			if doc["path"] == route:
				return frappe._dict(doc)


def get_index():
	return TestWrapper("test_frappe_website_index")


def get_documents():
	return [
		{
			"title": "Wikipedia",
			"path": "site/wikipedia",
			"content": """Wikipedia is a multilingual online encyclopedia created and maintained
			as an open collaboration project by a community of volunteer editors using a wiki-based editing system.
			It is the largest and most popular general reference work on the World Wide Web. CommonSearchTerm""",
		},
		{
			"title": "Linux",
			"path": "os/linux",
			"content": """Linux is a family of open source Unix-like operating systems based on the
			Linux kernel, an operating system kernel first released on September 17, 1991, by Linus Torvalds.
			Linux is typically packaged in a Linux distribution. CommonSearchTerm""",
		},
		{
			"title": "GNU",
			"path": "os/gnu",
			"content": """GNU is an operating system and an extensive collection of computer software.
			GNU is composed wholly of free software, most of which is licensed under the GNU Project's own
			General Public License. GNU is a recursive acronym for "GNU's Not Unix! ",
			chosen because GNU's design is Unix-like, but differs from Unix by being free software and containing no Unix code. CommonSearchTerm""",
		},
		{
			"title": "ERPNext",
			"path": "sw/erpnext",
			"content": """ERPNext is a free and open-source integrated Enterprise Resource Planning software developed by
			Frappe Technologies Pvt. Ltd. and is built on MariaDB database system using a Python based server-side framework.
			ERPNext is a generic ERP software used by manufacturers, distributors and services companies. CommonSearchTerm""",
		},
		{
			"title": "Frappe Framework",
			"path": "sw/frappe",
			"content": """Frappe Framework is a full-stack web framework, that includes everything you need to build and
			deploy business applications with Rich Admin Interface. CommonSearchTerm""",
		},
	]
