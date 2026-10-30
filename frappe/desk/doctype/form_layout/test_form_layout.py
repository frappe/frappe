# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.doctype.form_layout.form_layout import (
	deduplicate_names,
	get_form_layouts,
	parse_layout,
	save_form_layout,
)
from frappe.desk.form.load import get_new_doc
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

MANAGER = "test_form_layout_manager@example.com"
CREATOR = "test_form_layout_creator@example.com"
CREATE_ONLY_ROLE = "Test Form Layout Create Only"
READER = "test_form_layout_reader@example.com"
READ_ONLY_ROLE = "Test Form Layout Read Only"

QUICK_ENTRY_DT = "Test Create Quick Entry"
NO_MANDATORY_DT = "Test Create No Mandatory"
MANDATORY_TABLE_DT = "Test Create Mandatory Table"
FLAG_OFF_DT = "Test Create Flag Off"
PROMPT_DT = "Test Create Prompt"
HIDDEN_DT = "Test Create Hidden"
HIDDEN_PROMPT_DT = "Test Create Hidden Prompt"
HIDDEN_TABLE_DT = "Test Create Hidden Table"
HIDDEN_DOCTYPES = (HIDDEN_DT, HIDDEN_PROMPT_DT, HIDDEN_TABLE_DT)
OMITTED_DT = "Test Form Layout Omitted"


def make_layout(**kwargs):
	values = {"doctype": "Form Layout", "dt": "Note", "type": "Details", "layout": "[]"}
	values.update(kwargs)
	return frappe.get_doc(values)


def a_manager() -> str:
	if not frappe.db.exists("User", MANAGER):
		frappe.get_doc(
			doctype="User",
			email=MANAGER,
			first_name="Layout Manager",
			user_type="System User",
			roles=[{"role": "System Manager"}],
		).insert(ignore_permissions=True)
	return MANAGER


def a_creator() -> str:
	"""A user whose only role on the create doctypes grants create, not read."""
	return a_user_with_role(CREATOR, CREATE_ONLY_ROLE)


def a_reader() -> str:
	"""A user whose only role on the create doctypes grants read, not create."""
	return a_user_with_role(READER, READ_ONLY_ROLE)


def a_user_with_role(email: str, role: str) -> str:
	if not frappe.db.exists("Role", role):
		frappe.get_doc(doctype="Role", role_name=role, desk_access=1).insert()
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			doctype="User",
			email=email,
			first_name=role,
			user_type="System User",
			roles=[{"role": role}],
		).insert(ignore_permissions=True)
	return email


def make_create_doctype(name: str, fields: list[dict], **kwargs):
	permissions = [
		{"role": "System Manager", "read": 1, "write": 1, "create": 1},
		{"role": CREATE_ONLY_ROLE, "read": 0, "create": 1},
		{"role": READ_ONLY_ROLE, "read": 1, "write": 0, "create": 0, "delete": 0},
	]
	new_doctype(name, fields=fields, permissions=permissions, **kwargs).insert(ignore_if_duplicate=True)


def data(fieldname: str, **kwargs) -> dict:
	return {
		"label": fieldname.replace("_", " ").title(),
		"fieldname": fieldname,
		"fieldtype": "Data",
		**kwargs,
	}


def hide_field(dt: str, fieldname: str) -> None:
	"""Hide a mandatory field with no default, which DocType and Customize Form validation refuse."""
	frappe.make_property_setter(
		{"doctype": dt, "fieldname": fieldname, "property": "hidden", "value": 1, "property_type": "Check"},
		validate_fields_for_doctype=False,
	)


def quick_entry_fields(tabs: list) -> list:
	"""Each section's fields, with the condition it shows under."""
	return [
		(section.get("dependsOn"), [f for column in section["columns"] for f in column["fields"]])
		for tab in tabs
		for section in tab["sections"]
	]


def inline_layout(fields: list, type: str = "Quick Entry"):
	"""A Contact layout of one section holding `fields`."""
	tree = [{"name": "main", "columns": [{"fields": fields}]}]
	return make_layout(dt="Contact", type=type, layout=json.dumps(tree))


def published_doctypes(publish) -> list[str]:
	"""The doctypes named by each `doctype_update` sent through the patched publisher."""
	return [
		call.args[1]["doctype"]
		for call in publish.call_args_list
		if call.args[0] == "doctype_update" and call.kwargs.get("after_commit")
	]


class TestFormLayout(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_single_default_per_dt_and_type(self):
		make_layout().insert()
		self.assertRaises(frappe.ValidationError, make_layout().insert)

	def test_refuses_a_section_or_tab_named_like_a_field(self):
		section = [{"sections": [{"name": "title", "columns": [{"fields": ["content"]}]}]}]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(section)).insert)
		tab = [{"name": "public", "sections": [{"columns": [{"fields": ["content"]}]}]}]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(tab)).insert)
		# A break's fieldname is the section's own, as the meta fallback names it.
		own = [{"sections": [{"name": "seen_by_section", "columns": [{"fields": ["content"]}]}]}]
		make_layout(layout=json.dumps(own)).insert()

	def test_section_names_are_unique_across_tabs(self):
		twice = [
			{"name": "a", "sections": [{"name": "details", "columns": [{"fields": ["title"]}]}]},
			{"name": "b", "sections": [{"name": "details", "columns": [{"fields": ["content"]}]}]},
		]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(twice)).insert)
		tabs = parse_layout(json.dumps(twice))
		deduplicate_names(tabs)
		self.assertEqual([s["name"] for t in tabs for s in t["sections"]], ["details", "details-2"])

	def test_conditional_rows_coexist_with_default(self):
		make_layout().insert()
		make_layout(condition="doc.public").insert()
		make_layout(condition="doc.expire_notification_on").insert()

	def test_default_allowed_per_type(self):
		make_layout().insert()
		make_layout(type="Quick Entry").insert()

	def test_synthesizes_names_from_label_slug(self):
		tree = [{"sections": [{"label": "Contact  Details!", "columns": [{"fields": ["title"]}]}]}]
		tabs = parse_layout(json.dumps(tree))
		section = tabs[0]["sections"][0]
		self.assertEqual(section["name"], "contact_details")
		self.assertEqual(section["columns"][0]["name"], "column_1")

	def test_synthesizes_positional_names_and_dedupes(self):
		tree = [
			{
				"sections": [
					{"columns": []},
					{"label": "Details", "columns": []},
					{"name": "details", "columns": []},
				]
			}
		]
		sections = parse_layout(json.dumps(tree))[0]["sections"]
		self.assertEqual([s["name"] for s in sections], ["section_1", "details_2", "details"])

	def test_wraps_tabless_layout(self):
		tree = [{"label": "Details", "columns": [{"fields": ["title"]}]}]
		tabs = parse_layout(json.dumps(tree))
		self.assertEqual(tabs[0]["name"], "first_tab")
		self.assertEqual(tabs[0]["sections"][0]["name"], "details")

	def test_keeps_authored_names(self):
		tree = [{"name": "main", "sections": [{"name": "who", "columns": [{"name": "left", "fields": []}]}]}]
		tabs = parse_layout(json.dumps(tree))
		self.assertEqual(tabs[0]["name"], "main")
		self.assertEqual(tabs[0]["sections"][0]["name"], "who")
		self.assertEqual(tabs[0]["sections"][0]["columns"][0]["name"], "left")

	def test_fallback_is_deterministic(self):
		first = get_form_layouts("Note", "Details")["fallback"]
		second = get_form_layouts("Note", "Details")["fallback"]
		self.assertTrue(first)
		self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

	def test_names_are_stored_at_write_time(self):
		tree = [{"label": "Lead Details", "sections": [{"label": "Who", "columns": [{"fields": ["title"]}]}]}]
		doc = make_layout(layout=json.dumps(tree)).insert()
		stored = json.loads(frappe.db.get_value("Form Layout", doc.name, "layout"))
		self.assertEqual(stored[0]["name"], "lead_details")
		self.assertEqual(stored[0]["sections"][0]["name"], "who")
		self.assertEqual(stored[0]["sections"][0]["columns"][0]["name"], "column_1")

	def test_stored_name_survives_a_label_rename(self):
		tree = [{"label": "Lead Details", "sections": []}]
		doc = make_layout(layout=json.dumps(tree)).insert()
		stored = json.loads(doc.layout)
		stored[0]["label"] = "Everything Else"
		doc.layout = json.dumps(stored)
		doc.save()
		self.assertEqual(json.loads(doc.layout)[0]["name"], "lead_details")

	def test_tabless_layout_is_stored_without_a_wrapper(self):
		tree = [{"label": "Who", "columns": [{"fields": ["title"]}]}]
		doc = make_layout(layout=json.dumps(tree)).insert()
		stored = json.loads(doc.layout)
		self.assertEqual(len(stored), 1)
		self.assertEqual(stored[0]["name"], "who")
		self.assertNotIn("sections", stored[0])

	def test_duplicate_authored_names_are_rejected(self):
		tree = [{"name": "details", "sections": []}, {"name": "details", "sections": []}]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(tree)).insert)

	def test_duplicate_names_are_rejected_at_every_level(self):
		sections = [{"name": "who", "columns": []}, {"name": "who", "columns": []}]
		self.assertRaises(
			frappe.ValidationError, make_layout(layout=json.dumps([{"sections": sections}])).insert
		)
		columns = [{"name": "left", "fields": []}, {"name": "left", "fields": []}]
		tree = [{"sections": [{"columns": columns}]}]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(tree)).insert)

	def test_invalid_layout_is_rejected(self):
		self.assertRaises(frappe.ValidationError, make_layout(layout="{not json").insert)
		self.assertRaises(frappe.ValidationError, make_layout(layout='{"tabs": []}').insert)

	def test_deduplicate_names_repairs_a_synthesized_collision(self):
		# What `get_meta_layout` hits when a Tab Break's fieldname is literally `first_tab`.
		tabs = [{"name": "first_tab", "sections": []}, {"name": "first_tab", "sections": []}]
		deduplicate_names(tabs)
		self.assertEqual([tab["name"] for tab in tabs], ["first_tab", "first_tab-2"])

	def test_fallback_names_are_unique(self):
		tabs = get_form_layouts("Note", "Details")["fallback"]
		names = [tab["name"] for tab in tabs]
		self.assertEqual(len(names), len(set(names)))
		for tab in tabs:
			section_names = [section["name"] for section in tab["sections"]]
			self.assertEqual(len(section_names), len(set(section_names)))

	def test_saving_under_another_doctypes_name_is_refused(self):
		note_layout = make_layout().insert()
		with self.assertRaises(frappe.ValidationError):
			save_form_layout("ToDo", "Details", "[]", name=str(note_layout.name))
		self.assertEqual(frappe.db.get_value("Form Layout", note_layout.name, "dt"), "Note")

	def test_rejects_a_doctype_filter_posing_as_a_name(self):
		self.assertRaises(frappe.FrappeTypeError, get_form_layouts, ["!=", ""], "Details")
		self.assertRaises(frappe.FrappeTypeError, save_form_layout, "Note", "Details", "[]", name=["!=", ""])

	def test_rows_come_back_as_authored(self):
		tree = [{"name": "main", "sections": [{"name": "who", "columns": [{"fields": ["title"]}]}]}]
		make_layout(layout=json.dumps(tree)).insert()
		result = get_form_layouts("Note", "Details")
		self.assertEqual(len(result["layouts"]), 1)
		fields = result["layouts"][0]["layout"][0]["sections"][0]["columns"][0]["fields"]
		self.assertEqual(fields, ["title"])

	def test_a_save_announces_its_doctype(self):
		with set_user(a_manager()), patch("frappe.publish_realtime") as publish:
			make_layout().insert()
		self.assertEqual(published_doctypes(publish), ["Note"])

	def test_a_delete_announces_its_doctype(self):
		with set_user(a_manager()):
			layout = make_layout().insert()
			with patch("frappe.publish_realtime") as publish:
				layout.delete()
		self.assertEqual(published_doctypes(publish), ["Note"])

	def test_moving_a_layout_announces_both_doctypes(self):
		with set_user(a_manager()):
			layout = make_layout().insert()
			layout.dt = "ToDo"
			with patch("frappe.publish_realtime") as publish:
				layout.save()
		self.assertEqual(sorted(published_doctypes(publish)), ["Note", "ToDo"])


class TestOmittedFields(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		fields = [
			data("title", reqd=1),
			{"label": "Notes", "fieldname": "notes", "fieldtype": "Small Text"},
			{
				"label": "Status",
				"fieldname": "status",
				"fieldtype": "Select",
				"options": "Open\nClosed",
				"default": "Open",
				"reqd": 1,
			},
		]
		new_doctype(OMITTED_DT, fields=fields).insert(ignore_if_duplicate=True)
		# SQLite rolls back DDL, so each test's rollback would drop the DocType.
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.delete_doc_if_exists("DocType", OMITTED_DT)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.clear_messages()

	def tearDown(self):
		frappe.db.rollback()

	def save(self, omitted: list | None, name: str | int | None = None) -> str:
		return save_form_layout(
			OMITTED_DT,
			"Details",
			"[]",
			name=None if name is None else str(name),
			omitted=None if omitted is None else json.dumps(omitted),
		)

	def stored(self, name: str) -> list:
		return json.loads(frappe.db.get_value("Form Layout", name, "omitted") or "[]")

	def test_omits_optional_fields_and_mandatory_fields_with_a_default(self):
		name = self.save(["notes", "status"])
		self.assertEqual(self.stored(name), ["notes", "status"])
		self.assertEqual(
			get_form_layouts(OMITTED_DT, "Details")["layouts"][0]["omitted"], ["notes", "status"]
		)
		self.assertFalse(frappe.message_log)

	def test_refuses_a_mandatory_field_with_no_default_with_a_message(self):
		name = self.save(["title", "notes"])
		self.assertEqual(self.stored(name), ["notes"])
		self.assertIn("title", frappe.message_log[0]["message"])

	def test_refuses_an_entry_that_is_not_a_data_field(self):
		name = self.save(["gone", "notes"])
		self.assertEqual(self.stored(name), ["notes"])
		self.assertEqual(len(frappe.message_log), 1)

	def test_a_stale_entry_is_kept(self):
		name = self.save(["notes"])
		frappe.db.set_value("Form Layout", name, "omitted", json.dumps(["gone", "notes"]))
		self.save(["gone", "notes", "status"], name=name)
		self.assertEqual(self.stored(name), ["gone", "notes", "status"])
		self.assertFalse(frappe.message_log)

	def test_a_save_without_omitted_keeps_the_stored_list(self):
		name = self.save(["notes"])
		self.save(None, name=name)
		self.assertEqual(self.stored(name), ["notes"])
		self.save([], name=name)
		self.assertEqual(self.stored(name), [])

	def test_refuses_an_omitted_list_that_is_not_fieldnames(self):
		for omitted in ("{", '{"notes": 1}', "[1]"):
			with self.assertRaises(frappe.ValidationError):
				save_form_layout(OMITTED_DT, "Details", "[]", omitted=omitted)


class TestInlineFields(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user(a_manager())

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDown()

	def test_an_inline_field_may_replace_a_read_only_field(self):
		email = {"fieldname": "email_id", "label": "Email", "fieldtype": "Data", "options": "Email"}
		inline_layout(["first_name", email]).insert()
		section = get_form_layouts("Contact", "Quick Entry")["layouts"][0]["layout"][0]["sections"][0]
		self.assertEqual(section["columns"][0]["fields"], ["first_name", email])

	def test_refuses_an_inline_field_outside_a_create_layout(self):
		phone = {"fieldname": "phone", "fieldtype": "Data"}
		for type in ("Details", "Side Panel"):
			with self.assertRaisesRegex(frappe.ValidationError, "Only a Quick Entry or New Record layout"):
				inline_layout([phone], type=type).insert()

	def test_refuses_an_inline_field_without_a_name_or_type(self):
		for field in (
			{"fieldtype": "Data"},
			{"fieldname": "nickname"},
			{"fieldname": "", "fieldtype": "Data"},
			{"fieldname": ["!=", ""], "fieldtype": "Data"},
		):
			with self.assertRaisesRegex(frappe.ValidationError, "needs a fieldname and a fieldtype"):
				inline_layout([field]).insert()

	def test_refuses_an_inline_field_that_holds_no_single_value(self):
		for fieldtype in ("Section Break", "Table", "Button", "Unknown"):
			with self.assertRaisesRegex(frappe.ValidationError, "which a layout cannot define"):
				inline_layout([{"fieldname": "nickname", "fieldtype": fieldtype}]).insert()

	def test_refuses_an_inline_standard_field(self):
		for fieldname in ("name", "owner", "docstatus", "parent", "_assign"):
			with self.assertRaisesRegex(frappe.ValidationError, "standard field of every document"):
				inline_layout([{"fieldname": fieldname, "fieldtype": "Data"}]).insert()

	def test_refuses_an_inline_field_named_like_a_writable_field(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is already a field of Contact"):
			inline_layout([{"fieldname": "first_name", "fieldtype": "Data"}]).insert()

	def test_refuses_an_inline_field_placed_twice(self):
		email = {"fieldname": "email_id", "fieldtype": "Data"}
		for fields in ([email, email], ["email_id", email]):
			with self.assertRaisesRegex(frappe.ValidationError, "more than once"):
				inline_layout(fields).insert()

	def test_refuses_a_section_named_like_an_inline_field(self):
		nickname = {"fieldname": "nickname", "fieldtype": "Data"}
		tree = [{"name": "nickname", "columns": [{"fields": [nickname]}]}]
		layout = make_layout(dt="Contact", type="Quick Entry", layout=json.dumps(tree))
		self.assertRaisesRegex(frappe.ValidationError, "has the name of a field", layout.insert)


class TestCreateLayouts(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		a_creator()
		a_reader()
		make_create_doctype(
			QUICK_ENTRY_DT,
			[
				data("title", reqd=1),
				{"label": "Notes", "fieldname": "notes", "fieldtype": "Small Text"},
				{
					"label": "Status",
					"fieldname": "status",
					"fieldtype": "Select",
					"options": "Open\nClosed",
					"default": "Open",
					"reqd": 1,
				},
				data("city", mandatory_depends_on="eval:doc.status=='Closed'"),
				data("extra", allow_in_quick_entry=1),
				data("locked", reqd=1, read_only=1),
				data("computed", reqd=1, is_virtual=1),
				{
					"label": "More",
					"fieldname": "more_section",
					"fieldtype": "Section Break",
					"allow_in_quick_entry": 1,
				},
				data("after_break", reqd=1),
				{
					"label": "Roles",
					"fieldname": "roles",
					"fieldtype": "Table",
					"options": "Has Role",
					"mandatory_depends_on": "eval:doc.status=='Closed'",
				},
			],
			quick_entry=1,
		)
		make_create_doctype(
			NO_MANDATORY_DT,
			[data("title"), data("city", mandatory_depends_on="eval:doc.title")],
			quick_entry=1,
		)
		make_create_doctype(
			MANDATORY_TABLE_DT,
			[
				data("title", reqd=1),
				{
					"label": "Roles",
					"fieldname": "roles",
					"fieldtype": "Table",
					"options": "Has Role",
					"reqd": 1,
				},
			],
			quick_entry=1,
		)
		make_create_doctype(FLAG_OFF_DT, [data("title", reqd=1)], quick_entry=0)
		make_create_doctype(PROMPT_DT, [data("title")], quick_entry=1, autoname="Prompt")
		make_create_doctype(HIDDEN_DT, [data("code", reqd=1)], quick_entry=1)
		make_create_doctype(HIDDEN_PROMPT_DT, [data("code", reqd=1)], quick_entry=1, autoname="Prompt")
		make_create_doctype(
			HIDDEN_TABLE_DT,
			[
				data("title", reqd=1),
				{
					"label": "Roles",
					"fieldname": "roles",
					"fieldtype": "Table",
					"options": "Has Role",
					"reqd": 1,
				},
			],
			quick_entry=1,
		)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		for dt in (
			QUICK_ENTRY_DT,
			NO_MANDATORY_DT,
			MANDATORY_TABLE_DT,
			FLAG_OFF_DT,
			PROMPT_DT,
			*HIDDEN_DOCTYPES,
		):
			frappe.delete_doc_if_exists("DocType", dt)
		for user in (CREATOR, READER):
			frappe.delete_doc_if_exists("User", user)
		for role in (CREATE_ONLY_ROLE, READ_ONLY_ROLE):
			frappe.delete_doc_if_exists("Role", role)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def tearDown(self):
		frappe.db.rollback()

	def quick_entry(self, dt: str) -> dict:
		with set_user(a_manager()):
			return get_form_layouts(dt, "Quick Entry")

	def test_quick_entry_default_is_the_mandatory_set_in_doctype_order(self):
		self.assertEqual(
			quick_entry_fields(self.quick_entry(QUICK_ENTRY_DT)["fallback"]),
			[
				(None, ["title", "status"]),
				("eval:doc.status=='Closed'", ["city"]),
				(None, ["extra", "after_break"]),
				("eval:doc.status=='Closed'", ["roles"]),
			],
		)

	def test_quick_entry_sections_have_unique_names(self):
		sections = self.quick_entry(QUICK_ENTRY_DT)["fallback"][0]["sections"]
		self.assertEqual(
			[section["name"] for section in sections], ["section_1", "section_2", "section_3", "section_4"]
		)

	def test_quick_entry_default_does_not_read_the_flag(self):
		self.assertEqual(quick_entry_fields(self.quick_entry(FLAG_OFF_DT)["fallback"]), [(None, ["title"])])

	def test_quick_entry_default_with_no_fields_is_empty(self):
		self.assertEqual(self.quick_entry(PROMPT_DT)["fallback"], [])
		self.assertEqual(
			quick_entry_fields(self.quick_entry(NO_MANDATORY_DT)["fallback"]),
			[("eval:doc.title", ["city"])],
		)

	def test_dialog_flag(self):
		self.assertTrue(self.quick_entry(QUICK_ENTRY_DT)["dialog"])
		self.assertTrue(self.quick_entry(PROMPT_DT)["dialog"])
		self.assertFalse(self.quick_entry(NO_MANDATORY_DT)["dialog"])
		self.assertFalse(self.quick_entry(MANDATORY_TABLE_DT)["dialog"])
		self.assertFalse(self.quick_entry(FLAG_OFF_DT)["dialog"])

	def test_a_hidden_field_does_not_open_the_dialog(self):
		for dt, fieldname in zip(HIDDEN_DOCTYPES, ("code", "code", "roles"), strict=True):
			hide_field(dt, fieldname)
		self.assertFalse(self.quick_entry(HIDDEN_DT)["dialog"])
		self.assertTrue(self.quick_entry(HIDDEN_PROMPT_DT)["dialog"])
		self.assertFalse(self.quick_entry(HIDDEN_TABLE_DT)["dialog"])
		self.assertEqual(quick_entry_fields(self.quick_entry(HIDDEN_DT)["fallback"]), [(None, ["code"])])

	def test_a_quick_entry_row_opens_the_dialog(self):
		for dt in (NO_MANDATORY_DT, MANDATORY_TABLE_DT, FLAG_OFF_DT):
			make_layout(dt=dt, type="Quick Entry").insert()
			self.assertTrue(self.quick_entry(dt)["dialog"], dt)

	def test_a_quick_entry_row_comes_back_with_the_mandatory_fallback(self):
		tree = [{"sections": [{"name": "who", "columns": [{"fields": ["notes"]}]}]}]
		make_layout(dt=QUICK_ENTRY_DT, type="Quick Entry", layout=json.dumps(tree)).insert()
		result = self.quick_entry(QUICK_ENTRY_DT)
		self.assertEqual(len(result["layouts"]), 1)
		self.assertEqual(quick_entry_fields(result["layouts"][0]["layout"]), [(None, ["notes"])])
		self.assertEqual(quick_entry_fields(result["fallback"])[0], (None, ["title", "status"]))

	def test_only_quick_entry_carries_the_dialog_flag(self):
		with set_user(a_manager()):
			for type in ("Details", "Side Panel", "New Record"):
				self.assertNotIn("dialog", get_form_layouts(QUICK_ENTRY_DT, type), type)

	def test_new_record_falls_back_to_details_rows(self):
		tree = [{"name": "main", "sections": [{"name": "who", "columns": [{"fields": ["title"]}]}]}]
		details = make_layout(layout=json.dumps(tree)).insert()
		with set_user(a_manager()):
			result = get_form_layouts("Note", "New Record")
			self.assertEqual([row["name"] for row in result["layouts"]], [details.name])
			self.assertEqual(result["fallback"], get_form_layouts("Note", "Details")["fallback"])

	def test_a_new_record_row_replaces_the_details_rows(self):
		make_layout().insert()
		new_record = make_layout(type="New Record").insert()
		with set_user(a_manager()):
			result = get_form_layouts("Note", "New Record")
		self.assertEqual([row["name"] for row in result["layouts"]], [new_record.name])

	def test_create_layouts_accept_the_create_right_without_read(self):
		with set_user(a_creator()):
			self.assertTrue(get_form_layouts(QUICK_ENTRY_DT, "Quick Entry")["dialog"])
			self.assertTrue(get_form_layouts(QUICK_ENTRY_DT, "New Record")["fallback"])
			for type in ("Details", "Side Panel"):
				self.assertRaises(frappe.PermissionError, get_form_layouts, QUICK_ENTRY_DT, type)

	def test_create_layouts_accept_the_read_right_without_create(self):
		with set_user(a_reader()):
			self.assertTrue(get_form_layouts(QUICK_ENTRY_DT, "Quick Entry")["dialog"])
			self.assertTrue(get_form_layouts(QUICK_ENTRY_DT, "New Record")["fallback"])

	def test_create_layouts_refuse_without_read_or_create(self):
		with set_user(a_creator()):
			for type in ("Quick Entry", "New Record"):
				self.assertRaises(frappe.PermissionError, get_form_layouts, "Role", type)

	def test_new_doc_fills_defaults(self):
		with set_user(a_creator()):
			doc = get_new_doc(QUICK_ENTRY_DT)
		self.assertEqual(doc["doctype"], QUICK_ENTRY_DT)
		self.assertEqual(doc["status"], "Open")
		self.assertEqual(doc["owner"], CREATOR)
		self.assertFalse(frappe.db.count(QUICK_ENTRY_DT))

	def test_new_doc_needs_the_create_right(self):
		with set_user(a_creator()):
			self.assertRaises(frappe.PermissionError, get_new_doc, "Role")
		with set_user(a_reader()):
			self.assertRaises(frappe.PermissionError, get_new_doc, QUICK_ENTRY_DT)
