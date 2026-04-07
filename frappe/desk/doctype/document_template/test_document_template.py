# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.desk.doctype.document_template.document_template import (
	_check_user_permissions_on_template_data,
	get_permission_query_conditions,
	has_permission,
)
from frappe.tests import IntegrationTestCase


def make_template(
	reference_doctype="ToDo",
	template_name="Test Template",
	private=1,
	data=None,
	owner=None,
):
	"""Helper: insert a Document Template and return the doc."""
	if data is None:
		data = json.dumps({"doctype": reference_doctype, "description": "Test value"})

	doc = frappe.new_doc("Document Template")
	doc.reference_doctype = reference_doctype
	doc.template_name = template_name
	doc.private = private
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
	"""Integration tests for the Document Template DocType.

	Covers:
	  - validate(): duplicate name prevention, immutability of reference_doctype
	  - get_permission_query_conditions(): row-level filtering (visibility + doctype access)
	  - has_permission(): doc-level ownership rules + user permission checks on data
	  - Standard CRUD operations via frappe.get_doc / insert / save / delete_doc
	"""

	# ─── Fixtures ────────────────────────────────────────────────────────────

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

	# ─── validate() ──────────────────────────────────────────────────────────

	def test_validate_allows_private_same_name_different_users(self):
		"""Different users' private templates with the same name should be allowed."""
		make_template(template_name="Test Shared Name", private=1, owner=self.user1)
		make_template(template_name="Test Shared Name", private=1, owner=self.user2)

	def test_validate_blocks_public_duplicate_name(self):
		"""A public template name must be unique per doctype regardless of owner."""
		make_template(template_name="Test Public Dup", private=0, owner=self.user1)
		with self.assertRaises(frappe.ValidationError):
			make_template(template_name="Test Public Dup", private=0, owner=self.user2)

	def test_validate_allows_private_and_public_same_name(self):
		"""A private template may share a name with a public template (distinguished by lock icon)."""
		make_template(template_name="Test Mixed Name", private=0, owner=self.user1)
		# This should NOT raise — private and public can coexist with the same name
		make_template(template_name="Test Mixed Name", private=1, owner=self.user2)

	def test_validate_allows_same_name_for_different_doctypes(self):
		"""Same name, same owner, but different reference_doctype — allowed."""
		make_template(
			reference_doctype="ToDo",
			template_name="Test Standard",
			owner=self.user1,
		)
		make_template(
			reference_doctype="Note",
			template_name="Test Standard",
			owner=self.user1,
		)

	def test_validate_blocks_duplicate_private_name_same_owner(self):
		"""Duplicate private template name for same owner + same doctype must raise."""
		make_template(
			reference_doctype="ToDo",
			template_name="Test Duplicate",
			private=1,
			owner=self.user1,
		)
		with self.assertRaises(frappe.ValidationError):
			make_template(
				reference_doctype="ToDo",
				template_name="Test Duplicate",
				private=1,
				owner=self.user1,
			)

	def test_validate_data_must_be_valid_json(self):
		"""Non-JSON data should raise a ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			make_template(data="not-valid-json")

	# ─── reference_doctype immutability ──────────────────────────────────────

	def test_reference_doctype_cannot_be_changed(self):
		"""Changing reference_doctype after creation should raise."""
		tpl = make_template(reference_doctype="ToDo", template_name="Test Immutable Ref")
		tpl.reference_doctype = "Note"
		with self.assertRaises(frappe.ValidationError):
			tpl.save(ignore_permissions=True)

	def test_reference_doctype_unchanged_passes(self):
		"""Re-saving with the same reference_doctype should succeed."""
		tpl = make_template(reference_doctype="ToDo", template_name="Test Same Ref")
		tpl.template_name = "Test Same Ref Updated"
		tpl.save(ignore_permissions=True)
		self.assertEqual(tpl.template_name, "Test Same Ref Updated")

	# ─── get_permission_query_conditions() ───────────────────────────────────

	def test_perm_query_admin_gets_no_filter(self):
		"""Administrator should receive an empty string (no filter)."""
		result = get_permission_query_conditions("Administrator")
		self.assertEqual(result, "")

	def test_perm_query_system_manager_gets_no_filter(self):
		"""A System Manager user should receive an empty string."""
		sm_user = "test_system_manager@example.com"
		if not frappe.db.exists("User", sm_user):
			u = frappe.new_doc("User")
			u.email = sm_user
			u.first_name = "SM"
			u.send_welcome_email = 0
			u.insert(ignore_permissions=True)
			u.add_roles("System Manager")

		result = get_permission_query_conditions(sm_user)
		self.assertEqual(result, "")

	def test_perm_query_desk_user_filters_private_and_owner(self):
		"""A regular Desk User should get a filter limiting to public or own."""
		result = get_permission_query_conditions(self.user1)
		self.assertIn("private", result)
		self.assertIn(self.user1, result)

	def test_perm_query_includes_doctype_filter(self):
		"""Permission query should also filter by accessible doctypes."""
		result = get_permission_query_conditions(self.user1)
		self.assertIn("reference_doctype IN", result)

	def test_perm_query_uses_session_user_when_none_passed(self):
		"""Calling without a user argument should default to frappe.session.user."""
		frappe.set_user(self.user1)
		try:
			result = get_permission_query_conditions()
			self.assertIn(self.user1, result)
		finally:
			frappe.set_user("Administrator")

	def test_perm_query_hides_others_private_templates(self):
		"""user2's private template should NOT appear in user1's get_list."""
		private_tpl = make_template(
			template_name="Test User2 Private",
			private=1,
			owner=self.user2,
		)

		frappe.set_user(self.user1)
		try:
			names = frappe.get_list(
				"Document Template",
				filters={"reference_doctype": "ToDo"},
				pluck="name",
			)
		finally:
			frappe.set_user("Administrator")

		self.assertNotIn(private_tpl.name, names)

	def test_perm_query_shows_others_public_templates(self):
		"""user2's public template SHOULD appear in user1's get_list."""
		public_tpl = make_template(
			template_name="Test User2 Public",
			private=0,
			owner=self.user2,
		)

		frappe.set_user(self.user1)
		try:
			names = frappe.get_list(
				"Document Template",
				filters={"reference_doctype": "ToDo"},
				pluck="name",
			)
		finally:
			frappe.set_user("Administrator")

		self.assertIn(public_tpl.name, names)

	def test_perm_query_shows_own_private_templates(self):
		"""A user's own private template SHOULD appear in their own get_list."""
		own_tpl = make_template(
			template_name="Test User1 Own Private",
			private=1,
			owner=self.user1,
		)

		frappe.set_user(self.user1)
		try:
			names = frappe.get_list(
				"Document Template",
				filters={"reference_doctype": "ToDo"},
				pluck="name",
			)
		finally:
			frappe.set_user("Administrator")

		self.assertIn(own_tpl.name, names)

	# ─── has_permission() ────────────────────────────────────────────────────

	def _make_doc_stub(self, owner, private=1, reference_doctype="ToDo"):
		"""Return a lightweight object that mimics a Document Template doc."""

		class _DocStub:
			pass

		stub = _DocStub()
		stub.owner = owner
		stub.private = private
		stub.reference_doctype = reference_doctype
		return stub

	def test_has_permission_admin_always_allowed(self):
		doc = self._make_doc_stub(owner=self.user1)
		for ptype in ("read", "write", "delete", "create"):
			self.assertTrue(has_permission(doc, ptype, user="Administrator"))

	def test_has_permission_owner_always_allowed(self):
		doc = self._make_doc_stub(owner=self.user1)
		for ptype in ("read", "write", "delete"):
			self.assertTrue(has_permission(doc, ptype, user=self.user1))

	def test_has_permission_other_cannot_write_private(self):
		doc = self._make_doc_stub(owner=self.user1, private=1)
		self.assertFalse(has_permission(doc, "write", user=self.user2))

	def test_has_permission_other_cannot_delete_private(self):
		doc = self._make_doc_stub(owner=self.user1, private=1)
		self.assertFalse(has_permission(doc, "delete", user=self.user2))

	def test_has_permission_other_cannot_write_public(self):
		"""Even public templates cannot be written by non-owners."""
		doc = self._make_doc_stub(owner=self.user1, private=0)
		self.assertFalse(has_permission(doc, "write", user=self.user2))

	def test_has_permission_other_can_read_public_if_has_create_on_ref(self):
		"""user2 (Desk User) has create access to ToDo, so they can read public templates."""
		doc = self._make_doc_stub(owner=self.user1, private=0, reference_doctype="ToDo")
		self.assertTrue(has_permission(doc, "read", user=self.user2))

	# ─── Standard CRUD ───────────────────────────────────────────────────────

	def test_insert_creates_template(self):
		"""Standard insert via frappe.get_doc should create a template."""
		frappe.set_user(self.user1)
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Document Template",
					"reference_doctype": "ToDo",
					"template_name": "Test Insert",
					"private": 1,
					"data": json.dumps({"doctype": "ToDo", "description": "hello"}),
				}
			).insert()
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(frappe.db.exists("Document Template", doc.name))
		self.assertEqual(doc.owner, self.user1)

	def test_save_updates_data(self):
		"""Standard save should update the template data."""
		tpl = make_template(template_name="Test Save", owner=self.user1)
		new_data = json.dumps({"doctype": "ToDo", "description": "updated"})

		frappe.set_user(self.user1)
		try:
			tpl.data = new_data
			tpl.save()
		finally:
			frappe.set_user("Administrator")

		stored = frappe.db.get_value("Document Template", tpl.name, "data")
		self.assertEqual(stored, new_data)

	def test_save_blocked_for_non_owner(self):
		"""user2 should not be able to save user1's private template."""
		tpl = make_template(
			template_name="Test Save Block",
			private=1,
			owner=self.user1,
		)
		# Reload to clear the ignore_permissions flag set during insert
		tpl = frappe.get_doc("Document Template", tpl.name)
		frappe.set_user(self.user2)
		try:
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				tpl.data = json.dumps({"doctype": "ToDo", "description": "hacked"})
				tpl.save()
		finally:
			frappe.set_user("Administrator")

	def test_get_doc_returns_data(self):
		"""Standard get_doc should return the template with its data."""
		payload = {"doctype": "ToDo", "description": "read back test"}
		tpl = make_template(
			template_name="Test Read Back",
			data=json.dumps(payload),
			owner=self.user1,
		)

		frappe.set_user(self.user1)
		try:
			doc = frappe.get_doc("Document Template", tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(json.loads(doc.data), payload)

	def test_get_doc_blocked_for_others_private(self):
		"""user2 should not be able to read user1's private template."""
		tpl = make_template(
			template_name="Test Read Block",
			private=1,
			owner=self.user1,
		)

		frappe.set_user(self.user2)
		try:
			with self.assertRaises((frappe.PermissionError, frappe.DoesNotExistError)):
				frappe.get_doc("Document Template", tpl.name, check_permission=True)
		finally:
			frappe.set_user("Administrator")

	def test_get_doc_public_readable_by_others(self):
		"""user2 should be able to read user1's public template."""
		payload = {"doctype": "ToDo", "description": "public"}
		tpl = make_template(
			template_name="Test Read Public",
			private=0,
			data=json.dumps(payload),
			owner=self.user1,
		)

		frappe.set_user(self.user2)
		try:
			doc = frappe.get_doc("Document Template", tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(json.loads(doc.data), payload)

	def test_delete_by_owner(self):
		"""Owner should be able to delete their own template."""
		tpl = make_template(template_name="Test Delete Own", owner=self.user1)

		frappe.set_user(self.user1)
		try:
			frappe.delete_doc("Document Template", tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertFalse(frappe.db.exists("Document Template", tpl.name))

	def test_delete_blocked_for_non_owner(self):
		"""user2 should not be able to delete user1's private template."""
		tpl = make_template(
			template_name="Test Delete Block",
			private=1,
			owner=self.user1,
		)

		frappe.set_user(self.user2)
		try:
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				frappe.delete_doc("Document Template", tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(frappe.db.exists("Document Template", tpl.name))

	def test_delete_by_admin_always_works(self):
		tpl = make_template(template_name="Test Delete Admin", owner=self.user1)
		frappe.delete_doc("Document Template", tpl.name)
		self.assertFalse(frappe.db.exists("Document Template", tpl.name))

	# ─── Edge cases ──────────────────────────────────────────────────────────

	def test_create_and_read_round_trip(self):
		"""Data written via insert should be returned intact by get_doc."""
		payload = {
			"doctype": "ToDo",
			"description": "Round-trip test",
			"priority": "High",
		}

		frappe.set_user(self.user1)
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Document Template",
					"reference_doctype": "ToDo",
					"template_name": "Test Round Trip",
					"private": 1,
					"data": json.dumps(payload),
				}
			).insert()
			result = frappe.get_doc("Document Template", doc.name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(json.loads(result.data), payload)

	def test_multiple_templates_same_doctype_different_names(self):
		"""A user should be able to have multiple templates for the same doctype."""
		frappe.set_user(self.user1)
		try:
			d1 = frappe.get_doc(
				{
					"doctype": "Document Template",
					"reference_doctype": "ToDo",
					"template_name": "Test Multi A",
					"private": 1,
					"data": json.dumps({"doctype": "ToDo"}),
				}
			).insert()
			d2 = frappe.get_doc(
				{
					"doctype": "Document Template",
					"reference_doctype": "ToDo",
					"template_name": "Test Multi B",
					"private": 1,
					"data": json.dumps({"doctype": "ToDo"}),
				}
			).insert()
		finally:
			frappe.set_user("Administrator")

		self.assertNotEqual(d1.name, d2.name)
		self.assertTrue(frappe.db.exists("Document Template", d1.name))
		self.assertTrue(frappe.db.exists("Document Template", d2.name))

	def test_template_name_is_not_empty_string(self):
		"""An empty template_name should be rejected (reqd field)."""
		with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
			make_template(template_name="")

	def test_reference_doctype_is_required(self):
		"""A missing reference_doctype should be rejected."""
		with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
			make_template(reference_doctype="")

	# ─── User permission filtering on template data ──────────────────────────

	def _setup_user_permission(self, user, allow, for_value, applicable_for=None):
		"""Create a User Permission record and return it (auto-cleaned by rollback)."""
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

	def test_user_perm_check_passes_when_no_user_permissions(self):
		"""With no User Permission restrictions, all templates should pass."""
		from unittest.mock import patch

		data = json.dumps({"doctype": "ToDo", "role": "System Manager"})
		with patch(
			"frappe.core.doctype.user_permission.user_permission.get_user_permissions",
			return_value={},
		):
			self.assertTrue(_check_user_permissions_on_template_data(data, "ToDo", self.user1))

	def test_user_perm_check_passes_when_template_value_is_allowed(self):
		"""Template should pass when its link field value matches the user's allowed values."""
		self._setup_user_permission(self.user1, "Role", "Desk User")
		data = json.dumps({"doctype": "ToDo", "role": "Desk User"})
		self.assertTrue(_check_user_permissions_on_template_data(data, "ToDo", self.user1))

	def test_user_perm_check_fails_when_template_value_is_not_allowed(self):
		"""Template should fail when its link field value is not in the user's allowed set."""
		self._setup_user_permission(self.user1, "Role", "Desk User")
		data = json.dumps({"doctype": "ToDo", "role": "System Manager"})
		self.assertFalse(_check_user_permissions_on_template_data(data, "ToDo", self.user1))

	def test_user_perm_check_passes_when_template_field_is_empty(self):
		"""Empty template values should pass (non-strict mode skips empty)."""
		self._setup_user_permission(self.user1, "Role", "Desk User")
		data = json.dumps({"doctype": "ToDo", "description": "no role set"})
		self.assertTrue(_check_user_permissions_on_template_data(data, "ToDo", self.user1))

	def test_user_perm_check_passes_for_invalid_json(self):
		"""Gracefully handle invalid JSON data — should not block access."""
		self._setup_user_permission(self.user1, "Role", "Desk User")
		self.assertTrue(_check_user_permissions_on_template_data("not-json", "ToDo", self.user1))

	def test_user_perm_check_ignores_fields_with_ignore_user_permissions(self):
		"""Link fields marked ignore_user_permissions should be skipped."""
		self._setup_user_permission(self.user1, "User", self.user2)
		data = json.dumps({"doctype": "ToDo", "assigned_by": "some_other_user@example.com"})
		self.assertTrue(_check_user_permissions_on_template_data(data, "ToDo", self.user1))

	def test_has_permission_blocks_public_template_violating_user_perms(self):
		"""has_permission should block read of a public template that violates user permissions."""
		self._setup_user_permission(self.user2, "Role", "Desk User")
		tpl = make_template(
			template_name="Test User Perm Block",
			private=0,
			data=json.dumps({"doctype": "ToDo", "role": "System Manager"}),
			owner=self.user1,
		)
		self.assertFalse(has_permission(tpl, "read", user=self.user2))

	def test_has_permission_allows_public_template_matching_user_perms(self):
		"""has_permission should allow read of a public template that matches user permissions."""
		self._setup_user_permission(self.user2, "Role", "Desk User")
		tpl = make_template(
			template_name="Test User Perm Allow",
			private=0,
			data=json.dumps({"doctype": "ToDo", "role": "Desk User"}),
			owner=self.user1,
		)
		self.assertTrue(has_permission(tpl, "read", user=self.user2))

	def test_has_permission_owner_bypasses_user_perm_check(self):
		"""Owner should always have access regardless of user permissions on template data."""
		self._setup_user_permission(self.user1, "Role", "Desk User")
		tpl = make_template(
			template_name="Test Owner Bypass",
			private=0,
			data=json.dumps({"doctype": "ToDo", "role": "System Manager"}),
			owner=self.user1,
		)
		self.assertTrue(has_permission(tpl, "read", user=self.user1))

	def test_has_permission_admin_bypasses_user_perm_check(self):
		"""Administrator should always have access regardless of user permissions."""
		tpl = make_template(
			template_name="Test Admin Bypass UP",
			private=0,
			data=json.dumps({"doctype": "ToDo", "role": "System Manager"}),
			owner=self.user1,
		)
		self.assertTrue(has_permission(tpl, "read", user="Administrator"))

	def test_user_perm_applicable_for_is_respected(self):
		"""User Permission with applicable_for should only apply to that doctype."""
		self._setup_user_permission(self.user1, "Role", "Desk User", applicable_for="ToDo")
		data_todo = json.dumps({"doctype": "ToDo", "role": "System Manager"})
		self.assertFalse(_check_user_permissions_on_template_data(data_todo, "ToDo", self.user1))
		data_note = json.dumps({"doctype": "Note", "role": "System Manager"})
		self.assertTrue(_check_user_permissions_on_template_data(data_note, "Note", self.user1))
