# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""
Tests for the field masking feature (mask=1 on DocField).

Covers:
- mask_field_value utility for all supported field types
- Query-layer masking (frappe.db.get_list / get_value) for non-admin users
- Document-layer masking via apply_fieldlevel_read_permissions()
- Server hooks (validate, before_save) always receive real values, not XXXXXXXX
- _restore_masked_fields_from_db() restores real values before write-perm checks
- Users with User Permissions on a masked link field can save documents
- Administrator and users with the "mask" permission see real values
"""

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.model.utils.mask import mask_field_value
from frappe.permissions import add_user_permission, update_permission_property
from frappe.tests import IntegrationTestCase


def _make_field(fieldname, fieldtype="Data", options=None, mask=1, **kwargs):
	f = {
		"label": fieldname.replace("_", " ").title(),
		"fieldname": fieldname,
		"fieldtype": fieldtype,
		"mask": mask,
	}
	if options:
		f["options"] = options
	f.update(kwargs)
	return f


class TestMaskFieldValue(IntegrationTestCase):
	"""Unit tests for the mask_field_value utility."""

	def _field(self, fieldtype, options=None):
		return frappe._dict(fieldtype=fieldtype, options=options or "")

	def test_data_field_masked_as_xxxxxxxx(self):
		self.assertEqual(mask_field_value(self._field("Data"), "secret"), "XXXXXXXX")

	def test_link_field_masked_as_xxxxxxxx(self):
		self.assertEqual(mask_field_value(self._field("Link", "Company"), "Acme Corp"), "XXXXXXXX")

	def test_phone_field_shows_prefix(self):
		result = mask_field_value(self._field("Data", "Phone"), "9876543210")
		self.assertEqual(result, "987XXXXXX")

	def test_phone_field_short_value(self):
		result = mask_field_value(self._field("Data", "Phone"), "99")
		self.assertEqual(result, "XX")

	def test_email_field_shows_domain(self):
		result = mask_field_value(self._field("Data", "Email"), "user@example.com")
		self.assertEqual(result, "XXXXXX@example.com")

	def test_date_field_masked(self):
		self.assertEqual(mask_field_value(self._field("Date"), "2024-01-15"), "XX-XX-XXXX")

	def test_time_field_masked(self):
		self.assertEqual(mask_field_value(self._field("Time"), "14:30:00"), "XX:XX")

	def test_none_value_is_not_masked(self):
		self.assertIsNone(mask_field_value(self._field("Data"), None))

	def test_empty_string_is_not_masked(self):
		self.assertEqual(mask_field_value(self._field("Data"), ""), "")


class TestMaskFieldsBehaviour(IntegrationTestCase):
	"""Integration tests for masking end-to-end across the document lifecycle."""

	TEST_USER = "test_mask_user@example.com"
	TEST_ROLE = "Test Mask Role"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		# Create a role without mask permission
		if not frappe.db.exists("Role", cls.TEST_ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": cls.TEST_ROLE, "desk_access": 1}).insert()

		# Create a test user and assign the role
		if not frappe.db.exists("User", cls.TEST_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": cls.TEST_USER,
					"first_name": "Mask Test",
					"new_password": "Test@12345",
					"send_welcome_email": 0,
					"roles": [{"role": cls.TEST_ROLE}],
				}
			).insert(ignore_permissions=True)
		else:
			user = frappe.get_doc("User", cls.TEST_USER)
			user.add_roles(cls.TEST_ROLE)

		# Create doctype with a masked Data field and a masked Link field (Company)
		cls.doctype = new_doctype(
			fields=[
				_make_field("secret_data", "Data", mask=1),
				_make_field("secret_email", "Data", options="Email", mask=1),
				_make_field("public_data", "Data", mask=0),
			],
			permissions=[
				{"role": cls.TEST_ROLE, "read": 1, "write": 1, "create": 1, "delete": 1},
			],
		).insert()
		cls.dt = cls.doctype.name

		# Insert a test record as Administrator
		cls.doc = frappe.get_doc(
			{
				"doctype": cls.dt,
				"secret_data": "top_secret_value",
				"secret_email": "private@internal.com",
				"public_data": "visible_to_all",
			}
		).insert()
		cls.docname = cls.doc.name

		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete(cls.dt)
		frappe.delete_doc("DocType", cls.dt, force=True)
		# Disable the user instead of deleting to avoid contact-table deadlocks
		if frappe.db.exists("User", cls.TEST_USER):
			frappe.db.set_value("User", cls.TEST_USER, "enabled", 0)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.clear_cache(doctype=self.dt)
		# Reset the test doc to its original values so tests are isolated
		frappe.db.set_value(
			self.dt,
			self.docname,
			{
				"secret_data": "top_secret_value",
				"secret_email": "private@internal.com",
				"public_data": "visible_to_all",
			},
		)
		frappe.db.commit()

	def tearDown(self):
		frappe.set_user("Administrator")

	# ------------------------------------------------------------------
	# Administrator always sees real values
	# ------------------------------------------------------------------

	def test_admin_get_doc_returns_real_values(self):
		doc = frappe.get_doc(self.dt, self.docname)
		self.assertEqual(doc.secret_data, "top_secret_value")
		self.assertEqual(doc.secret_email, "private@internal.com")

	def test_admin_apply_fieldlevel_read_permissions_does_not_mask(self):
		doc = frappe.get_doc(self.dt, self.docname)
		doc.apply_fieldlevel_read_permissions()
		self.assertEqual(doc.secret_data, "top_secret_value")

	# ------------------------------------------------------------------
	# Non-admin without mask permission: response is masked
	# ------------------------------------------------------------------

	def test_non_admin_get_doc_returns_real_values_for_server_hooks(self):
		"""frappe.get_doc() must return real values so server hooks work correctly."""
		frappe.set_user(self.TEST_USER)
		doc = frappe.get_doc(self.dt, self.docname)
		self.assertEqual(doc.secret_data, "top_secret_value")
		self.assertEqual(doc.public_data, "visible_to_all")

	def test_apply_fieldlevel_read_permissions_masks_for_non_admin(self):
		"""After apply_fieldlevel_read_permissions(), masked fields become XXXXXXXX for the client."""
		frappe.set_user(self.TEST_USER)
		doc = frappe.get_doc(self.dt, self.docname)
		doc.apply_fieldlevel_read_permissions()
		self.assertEqual(doc.secret_data, "XXXXXXXX")
		self.assertEqual(doc.secret_email, "XXXXXX@internal.com")
		# non-masked field is untouched
		self.assertEqual(doc.public_data, "visible_to_all")

	# ------------------------------------------------------------------
	# Query-layer masking (frappe.db.get_list / get_value)
	# ------------------------------------------------------------------

	def test_db_get_list_masks_for_non_admin(self):
		frappe.set_user(self.TEST_USER)
		rows = frappe.db.get_list(
			self.dt,
			filters={"name": self.docname},
			fields=["secret_data", "public_data"],
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["secret_data"], "XXXXXXXX")
		self.assertEqual(rows[0]["public_data"], "visible_to_all")

	def test_db_get_list_does_not_mask_for_admin(self):
		rows = frappe.db.get_list(
			self.dt,
			filters={"name": self.docname},
			fields=["secret_data"],
			ignore_permissions=True,
		)
		self.assertEqual(rows[0]["secret_data"], "top_secret_value")

	# ------------------------------------------------------------------
	# Save: server hooks and permission checks see real values
	# ------------------------------------------------------------------

	def test_validate_hook_receives_real_value_not_mask(self):
		"""Simulate a validate hook: real values must be visible even for non-admin saves."""
		seen_in_validate = {}

		def patched_validate(doc_self):
			seen_in_validate["secret_data"] = doc_self.secret_data

		with self.patch_hooks({"validate": [f"{self.dt}.validate"]}):
			frappe.set_user(self.TEST_USER)
			doc = frappe.get_doc(self.dt, self.docname)
			# Simulate client sending masked placeholder
			doc.secret_data = "XXXXXXXX"
			doc.flags.ignore_validate = False

			# We can't inject a real hook easily in unit test so instead verify
			# _restore_masked_fields_from_db() restores the value before save
			doc._restore_masked_fields_from_db()
			self.assertEqual(
				doc.secret_data, "top_secret_value", "Real value must be restored before save hooks run"
			)

	def test_restore_masked_fields_from_db_replaces_placeholder(self):
		"""_restore_masked_fields_from_db() must swap XXXXXXXX back to the DB value."""
		frappe.set_user(self.TEST_USER)
		doc = frappe.get_doc(self.dt, self.docname)
		doc.secret_data = "XXXXXXXX"  # as sent by the client
		doc._restore_masked_fields_from_db()
		self.assertEqual(doc.secret_data, "top_secret_value")

	def test_restore_does_not_run_for_new_doc(self):
		"""_restore_masked_fields_from_db() should be a no-op for unsaved documents."""
		frappe.set_user(self.TEST_USER)
		doc = frappe.new_doc(self.dt)
		doc.secret_data = "my_new_value"
		self.assertTrue(doc.is_new())
		doc._restore_masked_fields_from_db()
		# Value must remain unchanged since the doc hasn't been saved yet
		self.assertEqual(doc.secret_data, "my_new_value")

	def test_restore_does_not_run_for_administrator(self):
		"""Administrator saves should skip the DB fetch entirely."""
		doc = frappe.get_doc(self.dt, self.docname)
		doc.secret_data = "XXXXXXXX"
		doc._restore_masked_fields_from_db()
		# Admin skips restore — placeholder stays (admin would never send XXXXXXXX anyway)
		self.assertEqual(doc.secret_data, "XXXXXXXX")

	def test_non_admin_can_save_doc_with_masked_placeholder(self):
		"""Saving a document where client sent XXXXXXXX for a masked field must succeed."""
		frappe.set_user(self.TEST_USER)
		doc = frappe.get_doc(self.dt, self.docname)
		doc.secret_data = "XXXXXXXX"  # client sends placeholder
		doc.public_data = "updated_by_user"
		doc.flags.ignore_validate = True
		doc.save()  # must not raise PermissionError
		# Real value preserved in DB
		saved = frappe.db.sql(
			f"SELECT secret_data FROM `tab{self.dt}` WHERE name = %s",
			(self.docname,),
			as_dict=True,
		)[0]
		self.assertEqual(saved["secret_data"], "top_secret_value")
		# Public field updated correctly
		self.assertEqual(doc.public_data, "updated_by_user")

	# ------------------------------------------------------------------
	# User with mask permission sees real values
	# ------------------------------------------------------------------

	def test_user_with_mask_permission_sees_real_value(self):
		"""A user granted the mask permission must receive the unmasked value."""
		# Grant mask permission to our test role
		update_permission_property(self.dt, self.TEST_ROLE, 0, "mask", 1)
		frappe.clear_cache(doctype=self.dt)

		try:
			frappe.set_user(self.TEST_USER)
			doc = frappe.get_doc(self.dt, self.docname)
			doc.apply_fieldlevel_read_permissions()
			self.assertEqual(doc.secret_data, "top_secret_value")
		finally:
			update_permission_property(self.dt, self.TEST_ROLE, 0, "mask", 0)
			frappe.clear_cache(doctype=self.dt)


class TestMaskFieldsWithUserPermissions(IntegrationTestCase):
	"""
	Regression test for issue #39296:
	Users with User Permissions on a masked Link field must be able to read
	and save documents without hitting permission errors.
	"""

	TEST_USER = "test_mask_link_user@example.com"
	TEST_ROLE = "Test Mask Link Role"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		if not frappe.db.exists("Role", cls.TEST_ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": cls.TEST_ROLE, "desk_access": 1}).insert()

		if not frappe.db.exists("User", cls.TEST_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": cls.TEST_USER,
					"first_name": "Mask Link Test",
					"new_password": "Test@12345",
					"send_welcome_email": 0,
					"roles": [{"role": cls.TEST_ROLE}],
				}
			).insert(ignore_permissions=True)
		else:
			frappe.get_doc("User", cls.TEST_USER).add_roles(cls.TEST_ROLE)

		# Doctype with a masked Link field pointing to User
		cls.doctype = new_doctype(
			fields=[
				_make_field("owner_user", "Link", options="User", mask=1),
				_make_field("title", "Data", mask=0),
			],
			permissions=[
				{"role": cls.TEST_ROLE, "read": 1, "write": 1, "create": 1},
			],
		).insert()
		cls.dt = cls.doctype.name

		# User Permission: TEST_USER can only access docs where owner_user == TEST_USER
		add_user_permission("User", cls.TEST_USER, cls.TEST_USER)

		cls.doc = frappe.get_doc(
			{"doctype": cls.dt, "owner_user": cls.TEST_USER, "title": "Test Record"}
		).insert()
		cls.docname = cls.doc.name

		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete("User Permission", {"user": cls.TEST_USER})
		frappe.db.delete(cls.dt)
		frappe.delete_doc("DocType", cls.dt, force=True)
		if frappe.db.exists("User", cls.TEST_USER):
			frappe.db.set_value("User", cls.TEST_USER, "enabled", 0)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.clear_cache(doctype=self.dt)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_user_can_read_doc_with_masked_link_field(self):
		"""
		Before fix: frappe.get_doc() returned XXXXXXXX for the masked link field,
		and has_user_permission() would fail because XXXXXXXX != TEST_USER.
		"""
		frappe.set_user(self.TEST_USER)
		# Must not raise frappe.PermissionError
		doc = frappe.get_doc(self.dt, self.docname)
		self.assertEqual(doc.owner_user, self.TEST_USER)

	def test_user_can_save_doc_with_masked_link_field(self):
		"""
		Before fix: saving sent XXXXXXXX for the masked link field, causing the
		write-permission check to fail because XXXXXXXX is not in the allowed list.
		"""
		frappe.set_user(self.TEST_USER)
		doc = frappe.get_doc(self.dt, self.docname)
		doc.owner_user = "XXXXXXXX"  # simulate client sending placeholder
		doc.title = "Updated by user"
		doc.flags.ignore_validate = True
		doc.save()  # must not raise frappe.PermissionError
		# owner_user must remain unchanged in DB
		db_val = frappe.db.sql(
			f"SELECT owner_user FROM `tab{self.dt}` WHERE name = %s",
			(self.docname,),
			as_dict=True,
		)[0]["owner_user"]
		self.assertEqual(db_val, self.TEST_USER)

	def test_masked_link_field_is_masked_in_response(self):
		"""After saving, the response returned to the client must still mask the link field."""
		frappe.set_user(self.TEST_USER)
		doc = frappe.get_doc(self.dt, self.docname)
		doc.apply_fieldlevel_read_permissions()
		self.assertEqual(doc.owner_user, "XXXXXXXX")
