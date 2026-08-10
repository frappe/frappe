# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.page.setup_wizard.install_fixtures import update_global_search_doctypes
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import make_test_objects
from frappe.utils import global_search, now_datetime


class TestGlobalSearch(IntegrationTestCase):
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
				doctype="Event", subject=text, repeat_on="Monthly", starts_on=now_datetime()
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
		results = global_search.web_search("login")
		self.assertTrue("login" in results[0].content)
		results = global_search.web_search(
			text="company", scope='manufacturing" UNION ALL SELECT 1,2,3,4,doctype from __global_search'
		)
		self.assertTrue(results == [])

	def test_rebuild_skips_virtual_doctypes(self):
		virtual_dt = "RQ Job"
		self.assertEqual(frappe.get_meta(virtual_dt).is_virtual, 1)

		frappe.cache.delete_value("doctypes_with_global_search")
		self.assertNotIn(virtual_dt, global_search.get_doctypes_with_global_search())

		frappe.db.delete("__global_search", {"doctype": virtual_dt})
		global_search.rebuild_for_doctype(virtual_dt)
		self.assertEqual(
			frappe.db.count("__global_search", {"doctype": virtual_dt}),
			0,
		)

	def test_migration_patch_clears_pre_existing_flags(self):
		import uuid

		from frappe.patches.v16_0.clear_global_search_flags_on_virtual_doctypes import execute

		dt_name = f"TestVirtualMigration-{uuid.uuid4().hex[:8]}"

		# Insert a valid virtual doctype WITHOUT the flags (validation would
		# otherwise reject it), then set the flags directly in the DB to
		# mimic pre-fix state that skips validation entirely.
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": dt_name,
				"module": "Custom",
				"is_virtual": 1,
				"custom": 1,
				"fields": [
					{"fieldname": "subject", "fieldtype": "Data", "label": "Subject"},
				],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			}
		).insert(ignore_permissions=True)

		# Simulate pre-fix state via direct DB writes (bypass validation).
		frappe.db.set_value("DocType", dt_name, "show_name_in_global_search", 1)
		frappe.db.set_value(
			"DocField",
			{"parent": dt_name, "fieldname": "subject"},
			"in_global_search",
			1,
		)
		# Simulate a Property Setter (Customize Form path).
		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocField",
				"doc_type": dt_name,
				"field_name": "subject",
				"property": "in_global_search",
				"property_type": "Check",
				"value": "1",
			}
		).insert(ignore_permissions=True)
		# Simulate a stale __global_search row.
		global_search.setup_global_search_table()
		global_search.sync_value(
			{
				"doctype": dt_name,
				"name": "unit-test-stale",
				"content": "should be removed",
				"published": 0,
				"title": "stale",
				"route": "",
			}
		)
		# sync_value would be blocked by our writer guard now — insert directly.
		frappe.db.sql(
			"""INSERT INTO `__global_search` (doctype, name, content, published, title, route)
			VALUES (%s, %s, %s, %s, %s, %s)""",
			(dt_name, "unit-test-stale", "should be removed", 0, "stale", ""),
		)
		frappe.db.commit()

		# Sanity: preconditions hold.
		self.assertEqual(frappe.db.get_value("DocType", dt_name, "show_name_in_global_search"), 1)
		self.assertEqual(
			frappe.db.get_value(
				"DocField",
				{"parent": dt_name, "fieldname": "subject"},
				"in_global_search",
			),
			1,
		)
		self.assertTrue(
			frappe.db.exists(
				"Property Setter",
				{"doc_type": dt_name, "property": "in_global_search"},
			)
		)
		self.assertGreaterEqual(
			frappe.db.count("__global_search", {"doctype": dt_name}),
			1,
		)

		# Run the patch.
		execute()
		frappe.db.commit()

		# Postconditions: flags cleared, Property Setter gone, index empty.
		self.assertEqual(frappe.db.get_value("DocType", dt_name, "show_name_in_global_search"), 0)
		self.assertEqual(
			frappe.db.get_value(
				"DocField",
				{"parent": dt_name, "fieldname": "subject"},
				"in_global_search",
			),
			0,
		)
		self.assertFalse(
			frappe.db.exists(
				"Property Setter",
				{"doc_type": dt_name, "property": "in_global_search"},
			)
		)
		self.assertEqual(frappe.db.count("__global_search", {"doctype": dt_name}), 0)

		settings = frappe.get_single("Global Search Settings")
		configured = {row.document_type for row in settings.allowed_in_global_search}
		self.assertNotIn(dt_name, configured)

		frappe.delete_doc("DocType", dt_name, force=True, ignore_permissions=True)

	def test_virtual_doctype_rejects_global_search_flags(self):
		import uuid

		dt_name = f"TestVirtualGSFlags-{uuid.uuid4().hex[:8]}"

		def _make_doc(**overrides):
			payload = {
				"doctype": "DocType",
				"name": dt_name,
				"module": "Custom",
				"is_virtual": 1,
				"custom": 1,
				"fields": [
					{"fieldname": "subject", "fieldtype": "Data", "label": "Subject"},
				],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			}
			payload.update(overrides)
			return frappe.get_doc(payload)

		with self.assertRaises(frappe.ValidationError):
			_make_doc(show_name_in_global_search=1).insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			_make_doc(
				fields=[
					{
						"fieldname": "subject",
						"fieldtype": "Data",
						"label": "Subject",
						"in_global_search": 1,
					}
				]
			).insert(ignore_permissions=True)

		doc = _make_doc().insert(ignore_permissions=True)
		self.assertEqual(doc.name, dt_name)

		frappe.delete_doc("DocType", dt_name, force=True, ignore_permissions=True)

	def test_settings_validate_rejects_virtual_doctype_row(self):
		# Client-side, the picker filters is_virtual=0, but a caller could
		# still POST an entry via /api/resource or a Server Script. Validate()
		# must reject virtual doctypes with a clear message.
		virtual_dt = "RQ Job"
		self.assertEqual(frappe.get_meta(virtual_dt).is_virtual, 1)

		settings = frappe.get_single("Global Search Settings")
		# snapshot the original list so we can restore it after the test
		original_rows = [row.document_type for row in settings.allowed_in_global_search]

		try:
			settings.append("allowed_in_global_search", {"document_type": virtual_dt})
			with self.assertRaises(frappe.ValidationError):
				settings.save(ignore_permissions=True)
		finally:
			# Restore the original list — remove the doctype we appended.
			settings.reload()
			settings.allowed_in_global_search = []
			for dt in original_rows:
				settings.append("allowed_in_global_search", {"document_type": dt})
			settings.save(ignore_permissions=True)

	def test_settings_ui_excludes_virtual_doctypes(self):
		from frappe.desk.doctype.global_search_settings.global_search_settings import (
			get_global_search_field_options,
			update_global_search_doctypes,
		)

		virtual_dt = "RQ Job"
		self.assertEqual(frappe.get_meta(virtual_dt).is_virtual, 1)

		update_global_search_doctypes()
		settings = frappe.get_single("Global Search Settings")
		configured = {row.document_type for row in settings.allowed_in_global_search}
		self.assertNotIn(virtual_dt, configured)

		with self.assertRaises(frappe.ValidationError):
			get_global_search_field_options(doctype=virtual_dt)

	def test_writer_guards_reject_virtual_doctype(self):
		virtual_dt = "RQ Job"
		frappe.db.delete("__global_search", {"doctype": virtual_dt})

		global_search.sync_value(
			{
				"doctype": virtual_dt,
				"name": "unit-test-virtual-row",
				"content": "should not be indexed",
				"published": 0,
				"title": "unit-test",
				"route": "",
			}
		)
		self.assertEqual(
			frappe.db.count("__global_search", {"doctype": virtual_dt}),
			0,
		)

		non_virtual_dt = "Event"
		frappe.db.delete("__global_search", {"name": "unit-test-nonvirtual-row"})
		global_search.sync_values(
			[
				(virtual_dt, "unit-test-virtual-row-2", "nope", 0, "vt", ""),
				(non_virtual_dt, "unit-test-nonvirtual-row", "kept", 0, "ok", ""),
			]
		)
		self.assertEqual(
			frappe.db.count("__global_search", {"doctype": virtual_dt}),
			0,
		)
		self.assertEqual(
			frappe.db.count("__global_search", {"name": "unit-test-nonvirtual-row"}),
			1,
		)

		frappe.db.delete("__global_search", {"name": "unit-test-nonvirtual-row"})
