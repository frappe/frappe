# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.page.setup_wizard.install_fixtures import update_global_search_doctypes
from frappe.test_runner import make_test_objects
from frappe.tests.utils import FrappeTestCase
from frappe.utils import global_search, now_datetime


class TestGlobalSearch(FrappeTestCase):
	def setUp(self):
		update_global_search_doctypes()
		global_search.setup_global_search_table()
		self.assertTrue("__global_search" in frappe.db.get_tables())
		doctype = "Event"
		global_search.reset()
		make_property_setter(doctype, "subject", "in_global_search", 1, "Int")
		make_property_setter(doctype, "event_type", "in_global_search", 1, "Int")
		make_property_setter(doctype, "roles", "in_global_search", 1, "Int")
		make_property_setter(doctype, "repeat_on", "in_global_search", 0, "Int")

	def tearDown(self):
		frappe.db.delete("Property Setter", {"doc_type": "Event"})
		frappe.clear_cache(doctype="Event")
		frappe.db.delete("Event")
		frappe.db.delete("__global_search")
		make_test_objects("Event")
		frappe.db.commit()

	def insert_test_events(self):
		frappe.db.delete("Event")
		phrases = [
			'"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.',
			"After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ",
			"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy.",
		]

		for text in phrases:
			frappe.get_doc(
				dict(doctype="Event", subject=text, repeat_on="Monthly", starts_on=now_datetime())
			).insert()

		global_search.sync_global_search()
		frappe.db.commit()

	def test_search(self):
		self.insert_test_events()
		results = global_search.search("awakens")
		self.assertTrue(
			"After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. "
			in results[0].content
		)

		results = global_search.search("extraterrestrial")
		self.assertTrue(
			"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy."
			in results[0].content
		)
		results = global_search.search("awakens & duty & alien")
		self.assertTrue(
			"After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. "
			in results[0].content
		)

	def test_update_doc(self):
		self.insert_test_events()
		test_subject = "testing global search"
		event = frappe.get_doc("Event", frappe.get_all("Event")[0].name)
		event.subject = test_subject
		event.save()
		frappe.db.commit()
		global_search.sync_global_search()
		results = global_search.search("testing global search")

		self.assertTrue("testing global search" in results[0].content)

	def test_update_fields(self):
		self.insert_test_events()
		results = global_search.search("Monthly")
		self.assertEqual(len(results), 0)
		doctype = "Event"
		make_property_setter(doctype, "repeat_on", "in_global_search", 1, "Int")
		global_search.rebuild_for_doctype(doctype)
		results = global_search.search("Monthly")
		self.assertEqual(len(results), 3)

	def test_delete_doc(self):
		self.insert_test_events()
		event_name = frappe.get_all("Event")[0].name
		event = frappe.get_doc("Event", event_name)
		test_subject = event.subject
		results = global_search.search(test_subject)
		self.assertTrue(
			any(r["name"] == event_name for r in results), msg="Failed to search document by exact name"
		)

		frappe.delete_doc("Event", event_name)
		global_search.sync_global_search()
		frappe.db.commit()

		results = global_search.search(test_subject)
		self.assertTrue(
			all(r["name"] != event_name for r in results),
			msg="Deleted documents appearing in global search.",
		)

	def test_insert_child_table(self):
		frappe.db.delete("Event")
		phrases = [
			"Hydrus is a small constellation in the deep southern sky. ",
			"It was first depicted on a celestial atlas by Johann Bayer in his 1603 Uranometria. ",
			"The French explorer and astronomer Nicolas Louis de Lacaille charted the brighter stars and gave their Bayer designations in 1756. ",
			'Its name means "male water snake", as opposed to Hydra, a much larger constellation that represents a female water snake. ',
			"It remains below the horizon for most Northern Hemisphere observers.",
			"The brightest star is the 2.8-magnitude Beta Hydri, also the closest reasonably bright star to the south celestial pole. ",
			"Pulsating between magnitude 3.26 and 3.33, Gamma Hydri is a variable red giant some 60 times the diameter of our Sun. ",
			"Lying near it is VW Hydri, one of the brightest dwarf novae in the heavens. ",
			"Four star systems have been found to have exoplanets to date, most notably HD 10180, which could bear up to nine planetary companions.",
		]

		for text in phrases:
			doc = frappe.get_doc({"doctype": "Event", "subject": text, "starts_on": now_datetime()})
			doc.insert()

		global_search.sync_global_search()
		frappe.db.commit()

	def test_get_field_value(self):
		cases = [
			{
				"case_type": "generic",
				"data": """
					<style type="text/css"> p.p1 {margin: 0.0px 0.0px 0.0px 0.0px; font: 14.0px 'Open Sans';
					-webkit-text-stroke: #000000} span.s1 {font-kerning: none} </style>
					<script>
					var options = {
						foo: "bar"
					}
					</script>
					<p class="p1"><span class="s1">Contrary to popular belief, Lorem Ipsum is not simply random text. It has
					roots in a piece of classical Latin literature from 45 BC, making it over 2000 years old. Richard McClintock,
					a Latin professor at Hampden-Sydney College in Virginia, looked up one of the more obscure Latin words, consectetur,
					from a Lorem Ipsum passage, and going through the cites of the word in classical literature, discovered the undoubtable source.
					Lorem Ipsum comes from sections 1.10.32 and 1.10.33 of "de Finibus Bonorum et Malorum" (The Extremes of Good and Evil) by Cicero,
					written in 45 BC. This book is a treatise on the theory of ethics, very popular during the Renaissance. The first line of Lorem Ipsum,
					"Lorem ipsum dolor sit amet..", comes from a line in section 1.10.32.</span></p>
					""",
				"result": (
					"Description : Contrary to popular belief, Lorem Ipsum is not simply random text. It has roots in a piece of classical "
					"Latin literature from 45 BC, making it over 2000 years old. Richard McClintock, a Latin professor at Hampden-Sydney College in Virginia, "
					"looked up one of the more obscure Latin words, consectetur, from a Lorem Ipsum passage, and going through the cites of the word "
					'in classical literature, discovered the undoubtable source. Lorem Ipsum comes from sections 1.10.32 and 1.10.33 of "de Finibus Bonorum '
					'et Malorum" (The Extremes of Good and Evil) by Cicero, written in 45 BC. This book is a treatise on the theory of ethics, very popular '
					'during the Renaissance. The first line of Lorem Ipsum, "Lorem ipsum dolor sit amet..", comes from a line in section 1.10.32.'
				),
			},
			{
				"case_type": "with_style",
				"data": """
					<style type="text/css"> p.p1 {margin: 0.0px 0.0px 0.0px 0.0px; font: 14.0px 'Open Sans';
					-webkit-text-stroke: #000000} span.s1 {font-kerning: none} </style>Lorem Ipsum Dolor Sit Amet
					""",
				"result": "Description : Lorem Ipsum Dolor Sit Amet",
			},
			{
				"case_type": "with_script",
				"data": """
					<script>
					var options = {
						foo: "bar"
					}
					</script>
					Lorem Ipsum Dolor Sit Amet
					""",
				"result": "Description : Lorem Ipsum Dolor Sit Amet",
			},
		]

		for case in cases:
			doc = frappe.get_doc(
				{
					"doctype": "Event",
					"subject": "Lorem Ipsum",
					"starts_on": now_datetime(),
					"description": case["data"],
				}
			)

			field_as_text = ""
			for field in doc.meta.fields:
				if field.fieldname == "description":
					field_as_text = global_search.get_formatted_value(doc.description, field)

			self.assertEqual(case["result"], field_as_text)

	def test_web_page_index(self):
		global_search.update_global_search_for_all_web_pages()
		global_search.sync_global_search()
		frappe.db.commit()
		results = global_search.web_search("unsubscribe")
		self.assertTrue("Unsubscribe" in results[0].content)
		results = global_search.web_search(
			text="unsubscribe", scope='manufacturing" UNION ALL SELECT 1,2,3,4,doctype from __global_search'
		)
		self.assertTrue(results == [])
