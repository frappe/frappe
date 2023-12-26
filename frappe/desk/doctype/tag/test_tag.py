import frappe
from frappe.desk.doctype.tag.tag import add_tag
from frappe.desk.listview import get_group_by_count
from frappe.tests.utils import FrappeTestCase


class TestTag(FrappeTestCase):
	def setUp(self) -> None:
		frappe.db.delete("Tag")
		frappe.db.sql("UPDATE `tabDocType` set _user_tags=''")

	@staticmethod
	def get_tag_count(filters=None):
		out = {}
		for tag in get_group_by_count("DocType", filters or "[]", "_user_tags"):
			out[tag["name"] or "No Tags"] = tag["count"]

		return out

	def test_tag_count_query(self):
		self.assertDictEqual(self.get_tag_count(), {"No Tags": frappe.db.count("DocType")})
		add_tag("Standard", "DocType", "User")
		add_tag("Standard", "DocType", "ToDo")

		# count with no filter
		self.assertDictEqual(
			self.get_tag_count(), {"No Tags": frappe.db.count("DocType") - 2, "Standard": 2}
		)

		# count with child table field filter
		self.assertDictEqual(
			self.get_tag_count(
				'[["DocField", "fieldname", "like", "%last_name%"], ["DocType", "name", "like", "%use%"]]'
			),
			{"Standard": 1},
		)
