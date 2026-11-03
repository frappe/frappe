from unittest.mock import patch

import frappe
from frappe.api.include import DOCUMENT_PARTS, serialize_meta
from frappe.api.link_marks import mark_of, readable_mark
from frappe.tests import IntegrationTestCase


class TestLinkMarks(IntegrationTestCase):
	def test_color_field_comes_before_image_field(self):
		# Event has a Color field and no image_field; User has an image_field and no `color`
		self.assertEqual(mark_of(frappe.get_meta("Event")), {"kind": "color", "field": "color"})
		self.assertEqual(mark_of(frappe.get_meta("User")), {"kind": "image", "field": "user_image"})
		self.assertIsNone(mark_of(frappe.get_meta("Note")))

	def test_meta_marks_a_link_by_its_target(self):
		fields = {df["fieldname"]: df for df in serialize_meta(frappe.get_meta("ToDo"))["fields"]}
		self.assertEqual(fields["allocated_to"]["link_mark"], {"kind": "image", "field": "user_image"})
		self.assertNotIn("link_mark", fields["description"])

	def test_meta_does_not_leak_a_mark_into_the_cached_meta(self):
		serialize_meta(frappe.get_meta("ToDo"))
		self.assertFalse(any("link_mark" in df.as_dict() for df in frappe.get_meta("ToDo").fields))

	def test_record_part_holds_the_target_value(self):
		user = frappe.get_doc("User", "Administrator")
		frappe.db.set_value("User", user.name, "user_image", "/files/test_link_marks.png")
		todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "link marks", "allocated_to": user.name}
		).insert()
		self.assertEqual(
			DOCUMENT_PARTS["link_marks"](todo), {"User::Administrator": "/files/test_link_marks.png"}
		)

	def test_target_field_the_reader_cannot_read_gives_no_mark(self):
		with self.set_user("Guest"):
			self.assertIsNone(readable_mark("User"))
		self.assertEqual(readable_mark("User"), {"kind": "image", "field": "user_image"})

	def test_an_unreadable_colour_falls_back_to_the_image(self):
		both = iter([{"kind": "color", "field": "color"}, {"kind": "image", "field": "user_image"}])
		with patch("frappe.api.link_marks.marks_of", return_value=both):
			with patch("frappe.api.link_marks.get_permitted_fields", return_value=["user_image"]):
				self.assertEqual(readable_mark("User"), {"kind": "image", "field": "user_image"})
