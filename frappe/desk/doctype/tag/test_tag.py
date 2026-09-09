import frappe
from frappe.desk.doctype.tag.tag import DocTags, add_tag
from frappe.desk.reportview import get_stats
from frappe.tests import IntegrationTestCase


class TestTag(IntegrationTestCase):
	def setUp(self) -> None:
		frappe.db.delete("Tag")
		frappe.db.sql("UPDATE `tabDocType` set _user_tags=''")

	def test_tag_count_query(self):
		self.assertDictEqual(
			get_stats('["_user_tags"]', "DocType"),
			{"_user_tags": [["No Tags", frappe.db.count("DocType")]]},
		)
		add_tag("Standard", "DocType", "User")
		add_tag("Standard", "DocType", "ToDo")

		# count with no filter
		self.assertDictEqual(
			get_stats('["_user_tags"]', "DocType"),
			{"_user_tags": [["Standard", 2], ["No Tags", frappe.db.count("DocType") - 2]]},
		)

		# count with child table field filter
		self.assertDictEqual(
			get_stats(
				'["_user_tags"]',
				"DocType",
				filters='[["DocField", "fieldname", "like", "%last_name%"], ["DocType", "name", "like", "%use%"]]',
			),
			{"_user_tags": [["Standard", 1], ["No Tags", 0]]},
		)

	def test_get_tags(self):
		doc = frappe.get_doc({"doctype": "ToDo", "description": "tag test"}).insert()
		doctags = DocTags(doc.doctype)

		self.assertEqual(doc.get_tags(), [])

		doctags.add(doc.name, "tag1")
		doc.reload()
		self.assertEqual(doc.get_tags(), ["tag1"])

		doctags.add(doc.name, "tag2")
		doctags.add(doc.name, "tag3")
		doc.reload()
		self.assertEqual(doc.get_tags(), ["tag1", "tag2", "tag3"])

	def test_get_tags_legacy_leading_comma_format(self):
		"""Pre-v16 sites stored _user_tags with a leading comma
		(',tag1,tag2'). Untouched old documents can still carry that
		format after upgrading -- get_tags() must handle both without
		a data patch."""
		doc = frappe.get_doc({"doctype": "ToDo", "description": "legacy tag test"}).insert()
		frappe.db.set_value(doc.doctype, doc.name, "_user_tags", ",tag1,tag2,tag3", update_modified=False)
		doc.reload()
		self.assertEqual(doc.get_tags(), ["tag1", "tag2", "tag3"])
