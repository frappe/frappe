# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.doctype.tag.tag import add_tag
from frappe.desk.doctype.tag_link.tag_link import has_tags
from frappe.tests import IntegrationTestCase


class TestTagLink(IntegrationTestCase):
	def test_first_tag_invalidates_cached_absence(self):
		frappe.db.delete("Tag Link", {"document_type": "ToDo"})
		frappe.client_cache.delete_value("doctype_has_tags::ToDo")
		self.assertFalse(has_tags("ToDo"))

		todo = frappe.get_doc({"doctype": "ToDo", "description": "Tag cache"}).insert()
		add_tag("Tag Cache", "ToDo", todo.name)

		self.assertTrue(has_tags("ToDo"))
