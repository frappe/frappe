# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.desk.doctype.document_template.document_template import (
	create_template,
	delete_template,
	get_permission_query_conditions,
	get_template_data,
	has_permission,
	update_template,
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
	  - validate(): duplicate name prevention
	  - get_permission_query_conditions(): row-level filtering
	  - has_permission(): doc-level ownership rules
	  - Whitelisted API: create_template, update_template,
	                     get_template_data, delete_template
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

	def test_validate_blocks_public_vs_private_duplicate_name(self):
		"""A private template cannot share a name with a public template for the same doctype."""
		make_template(template_name="Test Mixed Dup", private=0, owner=self.user1)
		with self.assertRaises(frappe.ValidationError):
			make_template(template_name="Test Mixed Dup", private=1, owner=self.user2)

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

	def test_validate_blocks_duplicate_name_same_owner_same_doctype(self):
		"""Duplicate name for same owner + same doctype must raise."""
		make_template(
			reference_doctype="ToDo",
			template_name="Test Duplicate",
			owner=self.user1,
		)
		with self.assertRaises(frappe.ValidationError):
			make_template(
				reference_doctype="ToDo",
				template_name="Test Duplicate",
				owner=self.user1,
			)

	def test_validate_data_must_be_valid_json(self):
		"""Non-JSON data should raise a ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			make_template(data="not-valid-json")

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
		self.assertIn(" OR ", result)

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

	def test_has_permission_blocked_when_no_ref_doctype(self):
		"""If reference_doctype is missing, non-owner non-admin should be blocked."""
		doc = self._make_doc_stub(owner=self.user1)
		doc.reference_doctype = None
		self.assertFalse(has_permission(doc, "read", user=self.user2))

	# ─── Whitelisted API: create_template ────────────────────────────────────

	def test_create_template_returns_name(self):
		frappe.set_user(self.user1)
		try:
			name = create_template(
				reference_doctype="ToDo",
				template_name="Test API Create",
				private=1,
				data=json.dumps({"doctype": "ToDo", "description": "hello"}),
			)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(frappe.db.exists("Document Template", name))

	def test_create_template_sets_owner_to_current_user(self):
		frappe.set_user(self.user1)
		try:
			name = create_template(
				reference_doctype="ToDo",
				template_name="Test Owner Check",
				private=1,
				data=json.dumps({"doctype": "ToDo"}),
			)
		finally:
			frappe.set_user("Administrator")

		owner = frappe.db.get_value("Document Template", name, "owner")
		self.assertEqual(owner, self.user1)

	def test_create_template_private_flag_stored_correctly(self):
		frappe.set_user(self.user1)
		try:
			name = create_template(
				reference_doctype="ToDo",
				template_name="Test Private Flag",
				private=0,
				data=json.dumps({"doctype": "ToDo"}),
			)
		finally:
			frappe.set_user("Administrator")

		private_val = frappe.db.get_value("Document Template", name, "private")
		self.assertEqual(private_val, 0)

	# ─── Whitelisted API: update_template ────────────────────────────────────

	def test_update_template_changes_data(self):
		tpl = make_template(template_name="Test Update", owner=self.user1)
		new_data = json.dumps({"doctype": "ToDo", "description": "updated"})

		frappe.set_user(self.user1)
		try:
			update_template(name=tpl.name, data=new_data)
		finally:
			frappe.set_user("Administrator")

		stored = frappe.db.get_value("Document Template", tpl.name, "data")
		self.assertEqual(stored, new_data)

	def test_update_template_blocked_for_non_owner(self):
		"""user2 should not be able to update user1's private template."""
		tpl = make_template(
			template_name="Test Update Block",
			private=1,
			owner=self.user1,
		)
		frappe.set_user(self.user2)
		try:
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				update_template(
					name=tpl.name,
					data=json.dumps({"doctype": "ToDo", "description": "hacked"}),
				)
		finally:
			frappe.set_user("Administrator")

	# ─── Whitelisted API: get_template_data ──────────────────────────────────

	def test_get_template_data_returns_stored_json(self):
		payload = {"doctype": "ToDo", "description": "read back test"}
		tpl = make_template(
			template_name="Test Read Back",
			data=json.dumps(payload),
			owner=self.user1,
		)

		frappe.set_user(self.user1)
		try:
			result = get_template_data(name=tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(json.loads(result), payload)

	def test_get_template_data_blocked_for_others_private(self):
		"""user2 should not be able to read user1's private template data."""
		tpl = make_template(
			template_name="Test Read Block",
			private=1,
			owner=self.user1,
		)

		frappe.set_user(self.user2)
		try:
			with self.assertRaises((frappe.PermissionError, frappe.DoesNotExistError)):
				get_template_data(name=tpl.name)
		finally:
			frappe.set_user("Administrator")

	def test_get_template_data_public_readable_by_others(self):
		"""user2 should be able to read user1's public template data."""
		payload = {"doctype": "ToDo", "description": "public"}
		tpl = make_template(
			template_name="Test Read Public",
			private=0,
			data=json.dumps(payload),
			owner=self.user1,
		)

		frappe.set_user(self.user2)
		try:
			result = get_template_data(name=tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(json.loads(result), payload)

	# ─── Whitelisted API: delete_template ────────────────────────────────────

	def test_delete_template_by_owner(self):
		tpl = make_template(template_name="Test Delete Own", owner=self.user1)

		frappe.set_user(self.user1)
		try:
			delete_template(name=tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertFalse(frappe.db.exists("Document Template", tpl.name))

	def test_delete_template_blocked_for_non_owner(self):
		"""user2 should not be able to delete user1's private template."""
		tpl = make_template(
			template_name="Test Delete Block",
			private=1,
			owner=self.user1,
		)

		frappe.set_user(self.user2)
		try:
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				delete_template(name=tpl.name)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(frappe.db.exists("Document Template", tpl.name))

	def test_delete_template_by_admin_always_works(self):
		tpl = make_template(template_name="Test Delete Admin", owner=self.user1)
		delete_template(name=tpl.name)
		self.assertFalse(frappe.db.exists("Document Template", tpl.name))

	# ─── Edge cases ──────────────────────────────────────────────────────────

	def test_create_and_immediately_apply_round_trip(self):
		"""Data written via create_template should be returned intact by get_template_data."""
		payload = {
			"doctype": "ToDo",
			"description": "Round-trip test",
			"priority": "High",
		}

		frappe.set_user(self.user1)
		try:
			name = create_template(
				reference_doctype="ToDo",
				template_name="Test Round Trip",
				private=1,
				data=json.dumps(payload),
			)
			result = get_template_data(name=name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(json.loads(result), payload)

	def test_multiple_templates_same_doctype_different_names(self):
		"""A user should be able to have multiple templates for the same doctype."""
		frappe.set_user(self.user1)
		try:
			n1 = create_template("ToDo", "Test Multi A", 1, json.dumps({"doctype": "ToDo"}))
			n2 = create_template("ToDo", "Test Multi B", 1, json.dumps({"doctype": "ToDo"}))
		finally:
			frappe.set_user("Administrator")

		self.assertNotEqual(n1, n2)
		self.assertTrue(frappe.db.exists("Document Template", n1))
		self.assertTrue(frappe.db.exists("Document Template", n2))

	def test_template_name_is_not_empty_string(self):
		"""An empty template_name should be rejected (reqd field)."""
		with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
			make_template(template_name="")

	def test_reference_doctype_is_required(self):
		"""A missing reference_doctype should be rejected."""
		with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
			make_template(reference_doctype="")
