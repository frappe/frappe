# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe.desk.doctype.document_template.document_template import (
	_check_user_permissions_on_template_data,
	_is_visible,
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
		data = json.dumps({"doctype": reference_doctype, "description": "Test value"})

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

	def _setup_user_permission(self, user, allow, for_value, applicable_for=None):
		"""Create a User Permission record (auto-cleaned by rollback)."""
		filters = {"user": user, "allow": allow, "for_value": for_value}
		if applicable_for:
			filters["applicable_for"] = applicable_for

		existing = frappe.db.exists("User Permission", filters)
		if existing:
			frappe.clear_cache()
			return frappe.get_doc("User Permission", existing)

		up = frappe.new_doc("User Permission")
		up.user = user
		up.allow = allow
		up.for_value = for_value
		if applicable_for:
			up.applicable_for = applicable_for
		up.insert(ignore_permissions=True)
		frappe.clear_cache()
		return up

	def test_validate_duplicate_name_rules(self):
		"""Validate uniqueness rules for template names."""
		# different users can have private templates with the same name
		make_template(template_name="Dup Name", private=1, owner=self.user1)
		make_template(template_name="Dup Name", private=1, owner=self.user2)

		# public template name must be unique per doctype
		make_template(template_name="Pub Dup", private=0, owner=self.user1)
		with self.assertRaises(frappe.ValidationError):
			make_template(template_name="Pub Dup", private=0, owner=self.user2)

		# private + public with same name is allowed
		make_template(template_name="Mixed", private=0, owner=self.user1)
		make_template(template_name="Mixed", private=1, owner=self.user2)

		# same name across different doctypes is allowed
		make_template(reference_doctype="ToDo", template_name="Cross DT", owner=self.user1)
		make_template(reference_doctype="Note", template_name="Cross DT", owner=self.user1)

		# duplicate private name for same owner + same doctype must raise
		make_template(template_name="Same Owner Dup", private=1, owner=self.user1)
		with self.assertRaises(frappe.ValidationError):
			make_template(template_name="Same Owner Dup", private=1, owner=self.user1)

	def test_validate_data_field(self):
		"""Data must be a valid non-empty JSON object."""
		for bad_data in ("not-valid-json", json.dumps([1, 2, 3]), json.dumps({}), "null"):
			with self.assertRaises(frappe.ValidationError):
				make_template(data=bad_data)

	def test_validate_required_fields(self):
		"""template_name and reference_doctype are mandatory."""
		with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
			make_template(template_name="")
		with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
			make_template(reference_doctype="")

	def test_permission_query_conditions(self):
		"""Admin/System Manager get no filter; regular users get 1=0."""
		self.assertEqual(get_permission_query_conditions("Administrator"), "")
		self.assertEqual(get_permission_query_conditions(self.user1), "1=0")

		# defaults to session user
		frappe.set_user(self.user1)
		try:
			self.assertEqual(get_permission_query_conditions(), "1=0")
		finally:
			frappe.set_user("Administrator")

	def test_get_list_respects_permission_query(self):
		"""Regular users see nothing via get_list; admin sees all."""
		tpl = make_template(template_name="List Test", private=1, owner=self.user1)

		# admin sees it
		names = frappe.get_list("Document Template", pluck="name")
		self.assertIn(tpl.name, names)

		# regular user sees nothing (1=0 blocks all)
		frappe.set_user(self.user2)
		try:
			names = frappe.get_list("Document Template", pluck="name")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(len(names), 0)

	def test_has_permission(self):
		"""Verify permission logic for admin, owner, and other users."""
		private_tpl = make_template(template_name="Perm Private", private=1, owner=self.user1)
		public_tpl = make_template(
			template_name="Perm Public",
			private=0,
			owner=self.user1,
			data=json.dumps({"doctype": "ToDo", "description": "pub"}),
		)

		# admin always allowed
		for ptype in ("read", "write", "delete", "create"):
			self.assertTrue(has_permission(private_tpl, ptype, user="Administrator"))

		# owner always allowed
		for ptype in ("read", "write", "delete"):
			self.assertTrue(has_permission(private_tpl, ptype, user=self.user1))

		# other user cannot access private template
		for ptype in ("read", "write", "delete"):
			self.assertFalse(has_permission(private_tpl, ptype, user=self.user2))

		# other user can read/select public but not write/delete
		self.assertTrue(has_permission(public_tpl, "read", user=self.user2))
		self.assertTrue(has_permission(public_tpl, "select", user=self.user2))
		self.assertFalse(has_permission(public_tpl, "write", user=self.user2))
		self.assertFalse(has_permission(public_tpl, "delete", user=self.user2))

		# defaults to session user
		frappe.set_user(self.user1)
		try:
			self.assertTrue(has_permission(private_tpl, "read"))
		finally:
			frappe.set_user("Administrator")

	def test_crud_operations(self):
		"""Insert, read, update, and delete round-trip."""
		payload = {"doctype": "ToDo", "description": "crud test", "priority": "High"}

		# insert
		frappe.set_user(self.user1)
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Document Template",
					"reference_doctype": "ToDo",
					"template_name": "CRUD Test",
					"private": 1,
					"data": json.dumps(payload),
				}
			).insert()
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(frappe.db.exists("Document Template", doc.name))
		self.assertEqual(doc.owner, self.user1)

		# read back
		frappe.set_user(self.user1)
		try:
			result = frappe.get_doc("Document Template", doc.name)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(json.loads(result.data), payload)

		# update
		new_data = json.dumps({"doctype": "ToDo", "description": "updated"})
		frappe.set_user(self.user1)
		try:
			doc.data = new_data
			doc.save()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Document Template", doc.name, "data"), new_data)

		# delete
		frappe.set_user(self.user1)
		try:
			frappe.delete_doc("Document Template", doc.name)
		finally:
			frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Document Template", doc.name))

	def test_crud_permission_enforcement(self):
		"""Non-owner cannot save, read, or delete another user's private template."""
		tpl = make_template(template_name="Blocked CRUD", private=1, owner=self.user1)
		tpl = frappe.get_doc("Document Template", tpl.name)

		frappe.set_user(self.user2)
		try:
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				tpl.data = json.dumps({"doctype": "ToDo", "description": "hacked"})
				tpl.save()

			with self.assertRaises((frappe.PermissionError, frappe.DoesNotExistError)):
				frappe.get_doc("Document Template", tpl.name, check_permission=True)

			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				frappe.delete_doc("Document Template", tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(frappe.db.exists("Document Template", tpl.name))

	def test_get_templates_api(self):
		"""Verify visibility and data stripping in get_templates."""
		make_template(template_name="GT Public", private=0, owner=self.user1)
		make_template(template_name="GT Private Other", private=1, owner=self.user2)
		make_template(template_name="GT Own Private", private=1, owner=self.user1)
		make_template(template_name="GT Disabled", disabled=1, private=0, owner=self.user1)

		frappe.set_user(self.user1)
		try:
			result = get_templates("ToDo")
		finally:
			frappe.set_user("Administrator")

		self.assertIn("templates", result)
		self.assertIn("has_next_page", result)
		self.assertIn("total", result)

		names = [t["template_name"] for t in result["templates"]]
		self.assertIn("GT Own Private", names)
		self.assertNotIn("GT Private Other", names)
		self.assertIn("GT Disabled", names)

		# data field should be stripped from response
		for t in result["templates"]:
			self.assertNotIn("data", t)

		# non-owner cannot see disabled
		frappe.set_user(self.user2)
		try:
			result = get_templates("ToDo")
		finally:
			frappe.set_user("Administrator")
		names2 = [t["template_name"] for t in result["templates"]]
		self.assertNotIn("GT Disabled", names2)

	def test_get_template_data_api(self):
		"""Verify access control on get_template_data."""
		payload = {"doctype": "ToDo", "description": "fetch test"}
		public_tpl = make_template(
			template_name="TD Public", data=json.dumps(payload), private=0, owner=self.user1
		)
		private_tpl = make_template(template_name="TD Private", private=1, owner=self.user1)

		# owner can access own private
		frappe.set_user(self.user1)
		try:
			raw = get_template_data(private_tpl.name)
			self.assertTrue(raw)
		finally:
			frappe.set_user("Administrator")

		# other user can access public, not private
		frappe.set_user(self.user2)
		try:
			self.assertEqual(json.loads(get_template_data(public_tpl.name)), payload)
			with self.assertRaises(frappe.PermissionError):
				get_template_data(private_tpl.name)
		finally:
			frappe.set_user("Administrator")

	def test_is_visible(self):
		"""Verify _is_visible filtering logic."""
		data = json.dumps({"doctype": "ToDo", "description": "val"})

		# disabled: hidden from others, shown to owner and admin
		disabled_t = frappe._dict(owner=self.user1, disabled=1, private=0, data="{}")
		self.assertFalse(_is_visible(disabled_t, self.user2, False, "ToDo"))
		self.assertTrue(_is_visible(disabled_t, self.user1, False, "ToDo"))
		self.assertTrue(_is_visible(disabled_t, "Administrator", True, "ToDo"))

		# private: hidden from others, shown to owner and admin
		private_t = frappe._dict(owner=self.user1, disabled=0, private=1, data="{}")
		self.assertFalse(_is_visible(private_t, self.user2, False, "ToDo"))
		self.assertTrue(_is_visible(private_t, self.user1, False, "ToDo"))
		self.assertTrue(_is_visible(private_t, "Administrator", True, "ToDo"))

		# public active: shown to all
		public_t = frappe._dict(owner=self.user1, disabled=0, private=0, data=data)
		self.assertTrue(_is_visible(public_t, self.user2, False, "ToDo"))

	def test_user_permission_filtering_on_template_data(self):
		"""Verify _check_user_permissions_on_template_data respects user permissions."""
		self._setup_user_permission(self.user1, "Role", "Desk User")

		# allowed value passes
		self.assertTrue(
			_check_user_permissions_on_template_data(
				json.dumps({"doctype": "ToDo", "role": "Desk User"}), "ToDo", self.user1
			)
		)
		# disallowed value fails
		self.assertFalse(
			_check_user_permissions_on_template_data(
				json.dumps({"doctype": "ToDo", "role": "System Manager"}), "ToDo", self.user1
			)
		)
		# empty field passes
		self.assertTrue(
			_check_user_permissions_on_template_data(
				json.dumps({"doctype": "ToDo", "description": "no role"}), "ToDo", self.user1
			)
		)
		# invalid/non-dict JSON passes gracefully
		self.assertTrue(_check_user_permissions_on_template_data("not-json", "ToDo", self.user1))
		self.assertTrue(_check_user_permissions_on_template_data(json.dumps([1, 2]), "ToDo", self.user1))

		# no user permissions -> passes
		with patch(
			"frappe.core.doctype.user_permission.user_permission.get_user_permissions",
			return_value={},
		):
			self.assertTrue(
				_check_user_permissions_on_template_data(
					json.dumps({"doctype": "ToDo", "role": "System Manager"}), "ToDo", self.user1
				)
			)

	def test_user_permission_applicable_for(self):
		"""applicable_for should scope user permission to that doctype only."""
		self._setup_user_permission(self.user1, "Role", "Desk User", applicable_for="ToDo")

		self.assertFalse(
			_check_user_permissions_on_template_data(
				json.dumps({"doctype": "ToDo", "role": "System Manager"}), "ToDo", self.user1
			)
		)
		self.assertTrue(
			_check_user_permissions_on_template_data(
				json.dumps({"doctype": "Note", "role": "System Manager"}), "Note", self.user1
			)
		)

	def test_has_permission_with_user_permissions(self):
		"""has_permission integrates user permission checks for non-owner reads."""
		self._setup_user_permission(self.user2, "Role", "Desk User")

		blocked = make_template(
			template_name="UP Blocked",
			private=0,
			data=json.dumps({"doctype": "ToDo", "role": "System Manager"}),
			owner=self.user1,
		)
		self.assertFalse(has_permission(blocked, "read", user=self.user2))

		allowed = make_template(
			template_name="UP Allowed",
			private=0,
			data=json.dumps({"doctype": "ToDo", "role": "Desk User"}),
			owner=self.user1,
		)
		self.assertTrue(has_permission(allowed, "read", user=self.user2))

		# owner and admin bypass user permission check
		self.assertTrue(has_permission(blocked, "read", user=self.user1))
		self.assertTrue(has_permission(blocked, "read", user="Administrator"))
