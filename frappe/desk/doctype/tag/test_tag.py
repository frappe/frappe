from unittest.mock import patch

import frappe
from frappe.desk.doctype.tag.tag import DocTags, add_tag, add_tags, ensure_tag, set_tag_color, update_record_tags
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

	def test_ensure_tag_creates_with_the_color(self):
		ensure_tag("coloured", "Red")
		self.assertEqual(frappe.db.get_value("Tag", "coloured", "color"), "Red")

	def test_ensure_tag_fills_a_tag_without_a_color(self):
		ensure_tag("plain")
		self.assertFalse(frappe.db.get_value("Tag", "plain", "color"))
		ensure_tag("plain", "Blue")
		self.assertEqual(frappe.db.get_value("Tag", "plain", "color"), "Blue")

	def test_ensure_tag_never_overwrites_a_color(self):
		ensure_tag("kept", "Green")
		ensure_tag("kept", "Red")
		self.assertEqual(frappe.db.get_value("Tag", "kept", "color"), "Green")

	def test_ensure_tag_rejects_an_unknown_color(self):
		with self.assertRaises(frappe.ValidationError):
			ensure_tag("odd", "Chartreuse")
		self.assertFalse(frappe.db.exists("Tag", "odd"))

	def test_set_tag_color_recolours_an_existing_tag(self):
		ensure_tag("repaint", "Red")
		frappe.set_user("test@example.com")
		self.addCleanup(frappe.set_user, "Administrator")
		set_tag_color("repaint", "Blue")
		self.assertEqual(frappe.db.get_value("Tag", "repaint", "color"), "Blue")

	def test_set_tag_color_rejects_an_unknown_color(self):
		ensure_tag("stays", "Red")
		with self.assertRaises(frappe.ValidationError):
			set_tag_color("stays", "Chartreuse")
		self.assertEqual(frappe.db.get_value("Tag", "stays", "color"), "Red")

	def test_update_record_tags_applies_adds_and_removes_in_one_call(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "batch tags"}).insert()
		add_tag("old", "ToDo", todo.name)
		answer = update_record_tags(
			"ToDo", todo.name, [{"tag": "fresh", "color": "Teal"}, {"tag": "plain"}], ["old"]
		)
		self.assertEqual(sorted(answer["tags"]), ["fresh", "plain"])
		self.assertEqual(answer["tag_colors"]["fresh"], "Teal")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "_user_tags"), "fresh,plain")

	def test_update_record_tags_changes_nothing_when_one_add_fails(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "batch tags"}).insert()
		add_tag("kept", "ToDo", todo.name)
		with self.assertRaises(frappe.ValidationError):
			update_record_tags(
				"ToDo", todo.name, [{"tag": "fine"}, {"tag": "odd", "color": "Chartreuse"}], ["kept"]
			)
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "_user_tags"), "kept")
		self.assertFalse(frappe.db.exists("Tag", "fine"))
		self.assertFalse(frappe.db.exists("Tag", "odd"))

	def test_update_record_tags_rolls_back_a_failure_mid_way(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "batch tags"}).insert()
		add_tag("kept", "ToDo", todo.name)
		with patch.object(DocTags, "add", side_effect=[None, frappe.ValidationError("boom")]):
			with self.assertRaises(frappe.ValidationError):
				update_record_tags("ToDo", todo.name, [{"tag": "a"}, {"tag": "b"}], ["kept"])
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "_user_tags"), "kept")

	def test_update_record_tags_needs_write_on_the_record(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "not yours"}).insert()
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		with self.assertRaises(frappe.PermissionError):
			update_record_tags("ToDo", todo.name, [{"tag": "sneaky"}], [])
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Tag", "sneaky"))

	def test_add_tag_and_add_tags_pass_the_color(self):
		first = frappe.get_doc({"doctype": "ToDo", "description": "colour test"}).insert()
		second = frappe.get_doc({"doctype": "ToDo", "description": "colour test"}).insert()
		add_tag("single", "ToDo", first.name, "Teal")
		add_tags(["bulk"], "ToDo", [first.name, second.name], "Violet")
		self.assertEqual(frappe.db.get_value("Tag", "single", "color"), "Teal")
		self.assertEqual(frappe.db.get_value("Tag", "bulk", "color"), "Violet")
		second.reload()
		self.assertEqual(second.get_tags(), ["bulk"])


class TestAdoptHelpdeskTagColor(IntegrationTestCase):
	def test_patch_drops_the_custom_field_and_keeps_the_colors(self):
		from frappe.patches.v17_0.adopt_helpdesk_tag_color import execute

		ensure_tag("helpdesk-tag", "Orange")
		# as Helpdesk installs it; a normal insert would clash with the standard field
		frappe.get_doc(
			{
				"doctype": "Custom Field",
				"name": "Tag-color",
				"dt": "Tag",
				"fieldname": "color",
				"fieldtype": "Select",
				"label": "Color",
				"options": frappe.get_meta("Tag").get_field("color").options,
			}
		).db_insert()
		execute()
		self.assertFalse(frappe.db.exists("Custom Field", {"dt": "Tag", "fieldname": "color"}))
		self.assertEqual(frappe.db.get_value("Tag", "helpdesk-tag", "color"), "Orange")
		self.assertFalse(frappe.get_meta("Tag").get_field("color").get("is_custom_field"))
