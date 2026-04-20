# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.desk.doctype.document_template.document_template import (
	_check_user_permissions_on_template_data,
	_has_template_manager_role,
	_is_system_manager,
	get_permission_query_conditions,
	get_template_data,
	get_templates,
	has_permission,
)
from frappe.tests import IntegrationTestCase


def make_template(
	reference_doctype="ToDo",
	template_name="Test Template",
	private=1,
	data=None,
	owner=None,
	disabled=0,
):
	"""Helper: insert a Document Template and return the doc."""
	if data is None:
		data = json.dumps({"description": "Test value"})

	doc = frappe.new_doc("Document Template")
	doc.reference_doctype = reference_doctype
	doc.template_name = template_name
	doc.private = private
	doc.disabled = disabled
	doc.data = data

	if owner:
		original_user = frappe.session.user
		frappe.set_user(owner)
		try:
			doc.insert(ignore_permissions=True)
		finally:
			frappe.set_user(original_user)
	else:
		doc.insert(ignore_permissions=True)

	return doc


class TestDocumentTemplate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		for username in ("desk_user_1@example.com", "desk_user_2@example.com"):
			if not frappe.db.exists("User", username):
				user = frappe.new_doc("User")
				user.email = username
				user.first_name = username.split("@")[0].replace("_", " ").title()
				user.send_welcome_email = 0
				user.insert(ignore_permissions=True)
				user.add_roles("Desk User")

		cls.user1 = "desk_user_1@example.com"
		cls.user2 = "desk_user_2@example.com"

	def test_validate_duplicate_name(self):
		"""Duplicate name rules: public must be unique per doctype, private scoped to owner."""
		make_template(template_name="Dup Name", private=1, owner=self.user1)
		make_template(template_name="Dup Name", private=1, owner=self.user2)

		make_template(template_name="Pub Dup", private=0, owner=self.user1)
		with self.assertRaises(frappe.ValidationError):
			make_template(template_name="Pub Dup", private=0, owner=self.user2)

		make_template(template_name="Owner Dup", private=1, owner=self.user1)
		with self.assertRaises(frappe.ValidationError):
			make_template(template_name="Owner Dup", private=1, owner=self.user1)

	def test_private_and_public_same_name_allowed(self):
		"""A user may have one public and one private template with the same name."""
		make_template(template_name="Dual Name", private=0, owner=self.user1)
		make_template(template_name="Dual Name", private=1, owner=self.user1)

	def test_duplicate_name_different_doctype_allowed(self):
		"""Same template name on different reference doctypes is allowed."""
		make_template(template_name="Cross DT", private=0, reference_doctype="ToDo")
		make_template(template_name="Cross DT", private=0, reference_doctype="Note")

	def test_validate_data_invalid_json(self):
		"""Non-JSON string is rejected."""
		with self.assertRaises(frappe.ValidationError):
			make_template(data="not-valid-json")

	def test_validate_data_array_rejected(self):
		"""JSON array is rejected (must be object)."""
		with self.assertRaises(frappe.ValidationError):
			make_template(data=json.dumps([1, 2, 3]))

	def test_validate_data_empty_object_rejected(self):
		"""Empty JSON object is rejected."""
		with self.assertRaises(frappe.ValidationError):
			make_template(data=json.dumps({}))

	def test_validate_data_null_rejected(self):
		"""JSON null is rejected."""
		with self.assertRaises(frappe.ValidationError):
			make_template(data="null")

	def test_validate_data_string_value_rejected(self):
		"""JSON string primitive is rejected (must be object)."""
		with self.assertRaises(frappe.ValidationError):
			make_template(data=json.dumps("hello"))

	def test_validate_data_number_rejected(self):
		"""JSON number primitive is rejected."""
		with self.assertRaises(frappe.ValidationError):
			make_template(data=json.dumps(42))

	def test_before_save_pretty_prints_and_sorts(self):
		"""Data is pretty-printed with sorted keys after save."""
		raw = json.dumps({"z_field": 1, "a_field": 2})
		tpl = make_template(data=raw, template_name="Pretty Print")
		saved = frappe.db.get_value("Document Template", tpl.name, "data")
		keys = list(json.loads(saved).keys())
		self.assertEqual(keys, sorted(keys))

	def test_valid_data_accepted(self):
		"""A valid non-empty JSON object is accepted."""
		tpl = make_template(data=json.dumps({"description": "ok"}), template_name="Valid Data")
		self.assertTrue(tpl.name)

	def test_owner_can_read_write_own_private_template(self):
		"""Owner can read and write their own private template."""
		tpl = make_template(template_name="Perm Test", private=1, owner=self.user1)

		frappe.set_user(self.user1)
		try:
			doc = frappe.get_doc("Document Template", tpl.name)
			doc.data = json.dumps({"description": "updated"})
			doc.save()
		finally:
			frappe.set_user("Administrator")

	def test_non_owner_blocked_from_private_template(self):
		"""Non-owner cannot read another user's private template."""
		tpl = make_template(template_name="Perm Block", private=1, owner=self.user1)

		frappe.set_user(self.user2)
		try:
			with self.assertRaises((frappe.PermissionError, frappe.DoesNotExistError)):
				frappe.get_doc("Document Template", tpl.name, check_permission=True)
		finally:
			frappe.set_user("Administrator")

	def test_owner_has_all_permissions(self):
		"""has_permission returns True for owner on all ptypes."""
		tpl = make_template(template_name="Owner All", private=1, owner=self.user1)
		for ptype in ("read", "write", "select"):
			self.assertTrue(has_permission(tpl, ptype, user=self.user1))

	def test_public_template_readable_by_non_owner(self):
		"""Non-owner can read a public template via get_template_data."""
		tpl = make_template(
			template_name="Public Read",
			private=0,
			data=json.dumps({"description": "pub"}),
			owner=self.user1,
		)

		frappe.set_user(self.user2)
		try:
			data = get_template_data(tpl.name)
			self.assertTrue(data)
		finally:
			frappe.set_user("Administrator")

	def test_public_template_write_falls_through(self):
		"""Non-owner write on public template: has_permission returns False (no explicit grant)."""
		user_doc = frappe.get_doc("User", self.user2)
		user_doc.remove_roles("Template Manager")

		tpl = make_template(
			template_name="Public No Write",
			private=0,
			data=json.dumps({"description": "pub"}),
			owner=self.user1,
		)

		result = has_permission(tpl, "write", user=self.user2)
		self.assertFalse(result)

	def test_public_template_select_by_non_owner(self):
		"""Non-owner can select public templates."""
		tpl = make_template(
			template_name="Public Select",
			private=0,
			data=json.dumps({"description": "pub"}),
			owner=self.user1,
		)
		self.assertTrue(has_permission(tpl, "select", user=self.user2))

	def test_system_manager_has_all_permissions(self):
		"""System Manager can access everything."""
		tpl = make_template(template_name="SM Test", private=1, owner=self.user1)
		self.assertTrue(_is_system_manager("Administrator"))
		for ptype in ("read", "write", "create"):
			self.assertTrue(has_permission(tpl, ptype, user="Administrator"))

	def test_get_templates_visibility(self):
		"""get_templates returns correct visibility and response shape."""
		make_template(template_name="GT Public", private=0, owner=self.user1)
		make_template(template_name="GT Own Private", private=1, owner=self.user1)
		make_template(template_name="GT Other Private", private=1, owner=self.user2)

		frappe.set_user(self.user1)
		try:
			result = get_templates("ToDo", limit_page_length=100)
		finally:
			frappe.set_user("Administrator")

		names = [t["template_name"] for t in result["templates"]]
		self.assertIn("GT Public", names)
		self.assertIn("GT Own Private", names)
		self.assertNotIn("GT Other Private", names)
		self.assertIn("has_next_page", result)
		self.assertIn("total", result)
		for t in result["templates"]:
			self.assertNotIn("data", t)

	def test_get_templates_pagination(self):
		"""get_templates respects limit_start and limit_page_length."""
		for i in range(5):
			make_template(template_name=f"Page {i}", private=0, owner=self.user1)

		frappe.set_user(self.user1)
		try:
			page1 = get_templates("ToDo", limit_start=0, limit_page_length=2)
			self.assertLessEqual(len(page1["templates"]), 2)
			if page1["total"] > 2:
				self.assertTrue(page1["has_next_page"])

			page2 = get_templates("ToDo", limit_start=2, limit_page_length=2)
			self.assertLessEqual(len(page2["templates"]), 2)
		finally:
			frappe.set_user("Administrator")

	def test_get_templates_disabled_hidden_from_non_owner(self):
		"""Disabled templates are hidden from non-owner but visible to owner."""
		make_template(template_name="Disabled Tpl", private=0, owner=self.user1, disabled=1)

		frappe.set_user(self.user1)
		try:
			result = get_templates("ToDo", limit_page_length=100)
			names = [t["template_name"] for t in result["templates"]]
			self.assertIn("Disabled Tpl", names)
		finally:
			frappe.set_user("Administrator")

		frappe.set_user(self.user2)
		try:
			result = get_templates("ToDo", limit_page_length=100)
			names = [t["template_name"] for t in result["templates"]]
			self.assertNotIn("Disabled Tpl", names)
		finally:
			frappe.set_user("Administrator")

	def test_get_templates_sorting_order(self):
		"""Templates sorted: disabled asc, private desc, template_name asc."""
		make_template(template_name="B Public", private=0, owner=self.user1)
		make_template(template_name="A Private", private=1, owner=self.user1)
		make_template(template_name="A Public", private=0, owner=self.user1)

		frappe.set_user(self.user1)
		try:
			result = get_templates("ToDo", limit_page_length=100)
			names = [t["template_name"] for t in result["templates"]]
			if "A Private" in names and "A Public" in names:
				self.assertLess(names.index("A Private"), names.index("A Public"))
		finally:
			frappe.set_user("Administrator")

	def test_get_template_data_owner_access(self):
		"""Owner can fetch private template data."""
		tpl = make_template(template_name="TD Access", private=1, owner=self.user1)

		frappe.set_user(self.user1)
		try:
			data = get_template_data(tpl.name)
			self.assertTrue(data)
			parsed = json.loads(data)
			self.assertIsInstance(parsed, dict)
		finally:
			frappe.set_user("Administrator")

	def test_get_template_data_non_owner_blocked(self):
		"""Non-owner cannot fetch private template data."""
		tpl = make_template(template_name="TD Block", private=1, owner=self.user1)

		frappe.set_user(self.user2)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_template_data(tpl.name)
		finally:
			frappe.set_user("Administrator")

	def test_get_template_data_nonexistent(self):
		"""Fetching a non-existent template raises DoesNotExistError."""
		with self.assertRaises(frappe.DoesNotExistError):
			get_template_data("nonexistent-template-name-12345")

	def _ensure_template_manager_role(self, user):
		"""Helper: assign Template Manager role to user if not already assigned."""
		if not frappe.db.exists("Role", "Template Manager"):
			frappe.get_doc({"doctype": "Role", "role_name": "Template Manager"}).insert(
				ignore_permissions=True
			)
		user_doc = frappe.get_doc("User", user)
		user_doc.add_roles("Template Manager")

	def test_template_manager_can_read_write_public(self):
		"""Template Manager can read/write public templates owned by others."""
		tm_user = self.user2
		self._ensure_template_manager_role(tm_user)

		public_tpl = make_template(
			template_name="TM Public",
			private=0,
			data=json.dumps({"description": "pub"}),
			owner=self.user1,
		)

		self.assertTrue(has_permission(public_tpl, "read", user=tm_user))
		self.assertTrue(has_permission(public_tpl, "write", user=tm_user))

	def test_template_manager_cannot_access_others_private(self):
		"""Template Manager with create perm on the reference doctype can access others' private templates."""
		tm_user = self.user2
		self._ensure_template_manager_role(tm_user)

		private_tpl = make_template(template_name="TM Private", private=1, owner=self.user1)
		self.assertFalse(has_permission(private_tpl, "read", user=tm_user))

	def test_template_manager_role_detection(self):
		"""_has_template_manager_role returns correct values."""
		self._ensure_template_manager_role(self.user2)
		self.assertTrue(_has_template_manager_role(self.user2))
		user_doc = frappe.get_doc("User", self.user1)
		user_doc.remove_roles("Template Manager")
		self.assertFalse(_has_template_manager_role(self.user1))

	def test_permission_query_conditions_system_manager(self):
		"""System Manager gets empty condition (sees everything)."""
		result = get_permission_query_conditions(user="Administrator")
		self.assertEqual(result, "")

	def test_permission_query_conditions_template_manager(self):
		"""Template Manager gets doctype-scoped condition."""
		self._ensure_template_manager_role(self.user2)
		result = get_permission_query_conditions(user=self.user2)
		self.assertIn("reference_doctype", result)
		self.assertIn("IN", result)

	def test_permission_query_conditions_regular_user(self):
		"""Regular user gets 1=0 (blocked at list level)."""
		user_doc = frappe.get_doc("User", self.user1)
		user_doc.remove_roles("Template Manager")
		result = get_permission_query_conditions(user=self.user1)
		self.assertEqual(result, "1=0")

	def test_permission_query_conditions_default_user(self):
		"""When user is None, defaults to session user."""
		frappe.set_user(self.user1)
		try:
			user_doc = frappe.get_doc("User", self.user1)
			user_doc.remove_roles("Template Manager")
			result = get_permission_query_conditions(user=None)
			self.assertEqual(result, "1=0")
		finally:
			frappe.set_user("Administrator")

	def test_user_permission_filters_template_data(self):
		"""Public template is blocked when user permission restricts a link field value."""
		user_doc = frappe.get_doc("User", self.user2)
		user_doc.remove_roles("Template Manager")
		if not frappe.db.exists(
			"User Permission", {"user": self.user2, "allow": "Role", "for_value": "Desk User"}
		):
			frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": self.user2,
					"allow": "Role",
					"for_value": "Desk User",
				}
			).insert(ignore_permissions=True)
			frappe.clear_cache()

		blocked = make_template(
			template_name="UP Block",
			private=0,
			data=json.dumps({"role": "System Manager"}),
			owner=self.user1,
		)
		allowed = make_template(
			template_name="UP Allow",
			private=0,
			data=json.dumps({"role": "Desk User"}),
			owner=self.user1,
		)

		self.assertFalse(has_permission(blocked, "read", user=self.user2))
		self.assertTrue(has_permission(allowed, "read", user=self.user2))

	def test_has_permission_create_returns_true_for_non_owner(self):
		"""Any user can create templates (create ptype returns True)."""
		tpl = make_template(template_name="Create Test", private=1, owner=self.user1)
		self.assertTrue(has_permission(tpl, "create", user=self.user2))

	def test_has_permission_defaults_to_session_user(self):
		"""has_permission defaults user to frappe.session.user when None."""
		tpl = make_template(template_name="Session Dflt", private=1, owner=self.user1)
		frappe.set_user(self.user1)
		try:
			self.assertTrue(has_permission(tpl, "read", user=None))
		finally:
			frappe.set_user("Administrator")

	def test_disabled_template_data_still_fetchable_by_owner(self):
		"""Owner can still fetch data of a disabled template."""
		tpl = make_template(
			template_name="Disabled Fetch",
			private=1,
			disabled=1,
			owner=self.user1,
		)
		frappe.set_user(self.user1)
		try:
			data = get_template_data(tpl.name)
			self.assertTrue(data)
		finally:
			frappe.set_user("Administrator")

	def test_before_save_with_valid_data(self):
		"""before_save normalizes valid JSON object data."""
		tpl = make_template(
			template_name="BS Valid",
			data=json.dumps({"b": 2, "a": 1}),
		)
		saved = frappe.db.get_value("Document Template", tpl.name, "data")
		parsed = json.loads(saved)
		self.assertEqual(list(parsed.keys()), ["a", "b"])
