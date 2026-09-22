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
)

TARGET = "Test WF MultiSelect Target"
ROW = "Test WF MultiSelect Row"
PARENT = "Test WF MultiSelect Parent"
NUMBERED = "Test WF MultiSelect Numbered"
NUMBERED_ROW = "Test WF MultiSelect Numbered Row"
UNTITLED = "Test WF MultiSelect Untitled"
UNTITLED_ROW = "Test WF MultiSelect Untitled Row"


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
		# integer names shown by title: the branch that ships raw JSON
		new_doctype(
			NUMBERED,
			fields=[{"fieldname": "title", "fieldtype": "Data", "label": "Title"}],
			autoname="autoincrement",
			title_field="title",
			show_title_field_in_link=1,
		).insert(ignore_if_duplicate=True)
		new_doctype(
			NUMBERED_ROW,
			istable=1,
			permissions=[],
			fields=[{"fieldname": "target", "fieldtype": "Link", "label": "Target", "options": NUMBERED}],
		).insert(ignore_if_duplicate=True)
		# integer names with no title field: the branch that ships a joined string
		new_doctype(
			UNTITLED,
			fields=[{"fieldname": "note", "fieldtype": "Data", "label": "Note"}],
			autoname="autoincrement",
		).insert(ignore_if_duplicate=True)
		new_doctype(
			UNTITLED_ROW,
			istable=1,
			permissions=[],
			fields=[{"fieldname": "target", "fieldtype": "Link", "label": "Target", "options": UNTITLED}],
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
				{
					"fieldname": "numbers",
					"fieldtype": "Table MultiSelect",
					"label": "Numbers",
					"options": NUMBERED_ROW,
				},
				{
					"fieldname": "untitled",
					"fieldtype": "Table MultiSelect",
					"label": "Untitled",
					"options": UNTITLED_ROW,
				},
			],
		).insert(ignore_if_duplicate=True)

		for title in ("Alpha", "Beta", "Gamma"):
			frappe.get_doc(doctype=TARGET, title=title).insert(ignore_if_duplicate=True)

		cls.numbered_names = [
			str(frappe.get_doc(doctype=NUMBERED, title=title).insert().name) for title in ("One", "Two")
		]
		cls.untitled_names = [
			str(frappe.get_doc(doctype=UNTITLED, note=note).insert().name) for note in ("First", "Second")
		]

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		for doctype in (PARENT, ROW, TARGET, NUMBERED_ROW, NUMBERED, UNTITLED_ROW, UNTITLED):
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
		self.assertIn("Alpha", self.link_options(web_form))

	def test_missing_child_doctype_does_not_break_the_form(self):
		self.assertEqual(get_table_multiselect_fields("Test WF No Such Row"), [])

	def test_has_link_option_descends_into_table_multiselect(self):
		fields = self.make_web_form().web_form_fields

		self.assertTrue(has_link_option(fields, TARGET))
		self.assertFalse(has_link_option(fields, "User"))

	def test_guest_gets_link_options_on_a_public_form(self):
		web_form = self.make_web_form()
		frappe.set_user("Guest")

		self.assertLessEqual({"Alpha", "Beta", "Gamma"}, set(self.link_options(web_form)))

	def test_key_required_form_needs_guest_read_on_the_link_doctype(self):
		"""The options are built with permissions ignored, so the form is the only allowlist."""
		web_form = self.make_web_form(key_required=1)
		key = self.make_web_form_request(web_form).key
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			self.link_options(web_form, web_form_request_key=key)

		frappe.set_user("Administrator")
		self.allow_guest_read(TARGET)
		frappe.set_user("Guest")

		self.assertIn("Alpha", self.link_options(web_form, web_form_request_key=key))

	def test_login_required_options_show_own_rows_unless_the_field_opts_out(self):
		user = self.make_website_user()
		own = frappe.get_doc(doctype=TARGET, title="Owned By TMS Website User").insert()
		self.addCleanup(frappe.delete_doc, TARGET, own.name, force=True)
		frappe.db.set_value(TARGET, own.name, "owner", user, update_modified=False)

		scoped = self.make_web_form(login_required=1)
		opted_out = self.make_web_form(login_required=1, field_settings={"allow_read_on_all_link_options": 1})
		frappe.set_user(user)

		self.assertEqual(self.link_options(scoped), [own.name])
		self.assertLessEqual({"Alpha", own.name}, set(self.link_options(opted_out)))

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

	def test_link_options_are_strings_for_an_autoincrement_doctype(self):
		"""The control matches with value.toLowerCase(), so an integer name throws on a keystroke."""
		web_form = self.make_web_form(link_field="numbers", options=NUMBERED_ROW)
		frappe.set_user("Guest")

		options = self.link_options(web_form, fieldname="numbers", raw=True)

		self.assertEqual(sorted(row["value"] for row in options), sorted(self.numbered_names))
		for row in options:
			self.assertIsInstance(row["value"], str)

	def test_link_options_join_for_an_autoincrement_doctype_without_a_title_field(self):
		"""Without a title field the options ship as one joined string, which integers break."""
		web_form = self.make_web_form(link_field="untitled", options=UNTITLED_ROW)
		frappe.set_user("Guest")

		options = self.link_options(web_form, fieldname="untitled", raw=True)

		# equality, not a subset: it pins the count, so an empty join cannot pass
		self.assertEqual(sorted(options), sorted(self.untitled_names))

	def make_web_form(self, field_settings=None, link_field="targets", options=ROW, **settings):
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
						"fieldname": link_field,
						"fieldtype": "Table MultiSelect",
						"label": link_field.title(),
						"options": options,
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

	def link_options(self, web_form, fieldname="targets", raw=False, **kwargs):
		"""The options the portal control filters in the browser, as the page ships them."""
		out = get_form_data(doctype=PARENT, web_form_name=web_form.name, **kwargs)
		field = next(f for f in out.web_form.web_form_fields if f.fieldname == fieldname)
		options = field.fields[0]["link_options"]
		if isinstance(options, str):
			options = options.split("\n") if options[0] != "[" else json.loads(options)
		if raw:
			return options
		return sorted(row["value"] if isinstance(row, dict) else row for row in options)

	def submit(self, web_form, targets):
		return accept(
			web_form=web_form.name,
			data=json.dumps({"doctype": PARENT, "title": "_Test TMS Submission", "targets": targets}),
		)
