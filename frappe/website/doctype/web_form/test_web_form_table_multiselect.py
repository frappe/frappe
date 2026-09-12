# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.core.doctype.doctype.doctype import clear_permissions_cache
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.permissions import add_permission, reset_perms
from frappe.tests import IntegrationTestCase
from frappe.website.doctype.web_form.web_form import (
	accept,
	get_form_data,
	get_table_multiselect_fields,
	has_link_option,
	search_web_form_link,
)

TARGET = "Test WF MultiSelect Target"
ROW = "Test WF MultiSelect Row"
PARENT = "Test WF MultiSelect Parent"


class TestWebFormTableMultiSelect(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		new_doctype(
			TARGET,
			fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title", "unique": 1}],
			autoname="field:title",
		).insert(ignore_if_duplicate=True)
		new_doctype(
			ROW,
			istable=1,
			permissions=[],
			fields=[{"fieldname": "target", "fieldtype": "Link", "label": "Target", "options": TARGET}],
		).insert(ignore_if_duplicate=True)
		new_doctype(
			PARENT,
			fields=[
				{"fieldname": "title", "fieldtype": "Data", "label": "Title"},
				{
					"fieldname": "targets",
					"fieldtype": "Table MultiSelect",
					"label": "Targets",
					"options": ROW,
				},
			],
		).insert(ignore_if_duplicate=True)

		for title in ("Alpha", "Beta", "Gamma"):
			frappe.get_doc(doctype=TARGET, title=title).insert(ignore_if_duplicate=True)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		for doctype in (PARENT, ROW, TARGET):
			frappe.delete_doc("DocType", doctype, force=True)
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.request = None

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.request = None

	def test_form_data_ships_the_child_link_docfield(self):
		"""The portal has no DocType meta, so the control needs the child's Link field as-is."""
		web_form = self.make_web_form()
		frappe.set_user("Guest")

		out = get_form_data(doctype=PARENT, web_form_name=web_form.name)

		field = next(f for f in out.web_form.web_form_fields if f.fieldname == "targets")
		self.assertEqual(
			[(df["fieldname"], df["fieldtype"], df["options"]) for df in field.fields],
			[("target", "Link", TARGET)],
		)

	def test_missing_child_doctype_does_not_break_the_form(self):
		self.assertEqual(get_table_multiselect_fields("Test WF No Such Row"), [])

	def test_has_link_option_descends_into_table_multiselect(self):
		fields = self.make_web_form().web_form_fields

		self.assertTrue(has_link_option(fields, TARGET))
		self.assertFalse(has_link_option(fields, "User"))

	def test_guest_can_search_link_targets_on_a_public_form(self):
		web_form = self.make_web_form()
		frappe.set_user("Guest")

		self.assertLessEqual({"Alpha", "Beta", "Gamma"}, set(self.search(web_form)))
		self.assertEqual(self.search(web_form, txt="alp"), ["Alpha"])

	def test_search_rejects_a_doctype_the_form_does_not_link_to(self):
		"""The query skips permissions, so the form's own fields are the only allowlist."""
		web_form = self.make_web_form()
		frappe.set_user("Guest")

		for doctype in ("User", "Test WF No Such DocType"):
			with self.subTest(doctype=doctype), self.assertRaises(frappe.PermissionError):
				self.search(web_form, doctype=doctype)

	def test_search_rejects_an_unpublished_form(self):
		web_form = self.make_web_form(published=0)
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			self.search(web_form)

	def test_search_requires_login_on_a_login_required_form(self):
		web_form = self.make_web_form(login_required=1)
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			self.search(web_form)

	def test_search_on_a_key_required_form_needs_a_key_and_guest_read(self):
		web_form = self.make_web_form(key_required=1)
		key = self.make_web_form_request(web_form).key
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			self.search(web_form, web_form_request_key=key)

		frappe.set_user("Administrator")
		self.allow_guest_read(TARGET)
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			self.search(web_form)
		self.assertIn("Alpha", self.search(web_form, web_form_request_key=key))

	def test_login_required_search_shows_own_rows_unless_the_field_opts_out(self):
		user = self.make_website_user()
		own = frappe.get_doc(doctype=TARGET, title="Owned By TMS Website User").insert()
		self.addCleanup(frappe.delete_doc, TARGET, own.name, force=True)
		frappe.db.set_value(TARGET, own.name, "owner", user, update_modified=False)

		scoped = self.make_web_form(login_required=1)
		opted_out = self.make_web_form(login_required=1, field_settings={"allow_read_on_all_link_options": 1})
		frappe.set_user(user)

		self.assertEqual(self.search(scoped), [own.name])
		self.assertLessEqual({"Alpha", own.name}, set(self.search(opted_out)))

	def test_guest_submission_still_validates_links_on_the_server(self):
		"""The client skips validate_link_and_fetch for guests, so the save must catch bad links."""
		web_form = self.make_web_form()
		frappe.set_user("Guest")

		with self.assertRaises(frappe.LinkValidationError):
			self.submit(web_form, [{"target": "Not A Real Target"}])

		doc = self.submit(web_form, [{"target": "Alpha"}])
		self.assertEqual([row.target for row in doc.targets], ["Alpha"])

	def test_required_table_multiselect_rejects_an_empty_list(self):
		web_form = self.make_web_form(field_settings={"reqd": 1})
		frappe.set_user("Guest")

		with self.assertRaises(frappe.ValidationError):
			self.submit(web_form, [])

	def make_web_form(self, field_settings=None, **settings):
		"""Unique names keep get_cached_doc from serving a stale form."""
		suffix = frappe.generate_hash(length=8)
		web_form = frappe.get_doc(
			{
				"doctype": "Web Form",
				"title": f"_Test TMS Web Form {suffix}",
				"route": f"test-tms-web-form-{suffix}",
				"doc_type": PARENT,
				"module": "Website",
				"published": 1,
				"login_required": 0,
				"web_form_fields": [
					{"fieldname": "title", "fieldtype": "Data", "label": "Title"},
					{
						"fieldname": "targets",
						"fieldtype": "Table MultiSelect",
						"label": "Targets",
						"options": ROW,
						**(field_settings or {}),
					},
				],
				**settings,
			}
		).insert(ignore_permissions=True)

		self.addCleanup(frappe.delete_doc, "Web Form", web_form.name, force=True, ignore_permissions=True)
		return web_form

	def make_web_form_request(self, web_form):
		return frappe.get_doc(
			{
				"doctype": "Web Form Request",
				"web_form": web_form.name,
				"web_form_values": json.dumps({}),
				"doc_values": json.dumps({}),
			}
		).insert(ignore_permissions=True)

	def make_website_user(self):
		email = "tms-web-form-user@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": "TMS", "user_type": "Website User"}
			).insert(ignore_permissions=True)
		return email

	def allow_guest_read(self, doctype):
		add_permission(doctype, "Guest", ptype="read")
		clear_permissions_cache(doctype)
		self.addCleanup(lambda: (reset_perms(doctype), clear_permissions_cache(doctype)))

	def search(self, web_form, doctype=TARGET, txt="", **kwargs):
		results = search_web_form_link(web_form_name=web_form.name, doctype=doctype, txt=txt, **kwargs)
		return sorted(row["value"] for row in results)

	def submit(self, web_form, targets):
		return accept(
			web_form=web_form.name,
			data=json.dumps({"doctype": PARENT, "title": "_Test TMS Submission", "targets": targets}),
		)
