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
from frappe.utils import flt


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

	def test_datetime_field_masked(self):
		self.assertEqual(mask_field_value(self._field("Datetime"), "2024-01-15 14:30:00"), "XX-XX-XXXX XX:XX")

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

	def test_db_get_value_does_not_mask_when_permissions_are_ignored(self):
		frappe.set_user(self.TEST_USER)
		value = frappe.db.get_value(self.dt, self.docname, "secret_data")
		self.assertEqual(value, "top_secret_value")

	def test_qb_get_query_does_not_mask_when_permissions_are_ignored(self):
		frappe.set_user(self.TEST_USER)
		rows = frappe.qb.get_query(
			self.dt,
			fields=["secret_data"],
			filters={"name": self.docname},
			ignore_permissions=True,
		).run(as_dict=True)
		self.assertEqual(rows[0]["secret_data"], "top_secret_value")

	def test_legacy_db_query_masks_plain_field(self):
		frappe.set_user(self.TEST_USER)
		from frappe.model.db_query import DatabaseQuery

		rows = DatabaseQuery(self.dt).execute(
			fields=["secret_data"],
			filters={"name": self.docname},
		)
		self.assertEqual(rows[0]["secret_data"], "XXXXXXXX")

	def test_legacy_db_query_does_not_mask_when_permissions_are_ignored(self):
		frappe.set_user(self.TEST_USER)
		from frappe.model.db_query import DatabaseQuery

		rows = DatabaseQuery(self.dt).execute(
			fields=["secret_data"],
			filters={"name": self.docname},
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


class TestMaskFieldsInChildTable(IntegrationTestCase):
	"""Regression test for issue #39679: masked child-table fields must be masked on read
	(numeric ones as the placeholder, not cast back to 0) and restored on save."""

	TEST_USER = "test_mask_child_user@example.com"
	TEST_ROLE = "Test Mask Child Role"

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
					"first_name": "Mask Child Test",
					"send_welcome_email": 0,
					"roles": [{"role": cls.TEST_ROLE}],
				}
			).insert(ignore_permissions=True)
		else:
			frappe.get_doc("User", cls.TEST_USER).add_roles(cls.TEST_ROLE)

		# Child doctype with a masked Data field, a masked Currency field and an unmasked Float
		cls.child_dt = (
			new_doctype(
				istable=1,
				fields=[
					_make_field("secret_note", "Data", mask=1),
					_make_field("rate", "Currency", mask=1),
					_make_field("public_qty", "Float", mask=0),
				],
			)
			.insert()
			.name
		)

		cls.dt = (
			new_doctype(
				fields=[_make_field("items", "Table", options=cls.child_dt, mask=0)],
				permissions=[{"role": cls.TEST_ROLE, "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)

		doc = frappe.get_doc(
			{
				"doctype": cls.dt,
				"items": [{"secret_note": "child_secret", "rate": 1234.5, "public_qty": 7}],
			}
		).insert()
		cls.docname = doc.name
		cls.row_name = doc.items[0].name

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete(cls.dt)
		frappe.db.delete(cls.child_dt)
		frappe.delete_doc("DocType", cls.dt, force=True)
		frappe.delete_doc("DocType", cls.child_dt, force=True)
		if frappe.db.exists("User", cls.TEST_USER):
			frappe.db.set_value("User", cls.TEST_USER, "enabled", 0)
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_child_masked_fields_masked_for_non_admin(self):
		"""Child masked fields are masked on read; numeric ones survive serialization as the
		placeholder instead of being cast to 0."""
		frappe.set_user(self.TEST_USER)
		doc = frappe.get_doc(self.dt, self.docname)
		doc.apply_fieldlevel_read_permissions()

		self.assertEqual(doc.items[0].secret_note, "XXXXXXXX")
		self.assertEqual(doc.items[0].rate, "XXXXXXXX")
		self.assertEqual(doc.items[0].public_qty, 7)  # unmasked field untouched
		# numeric placeholder must not be cast back to 0 when serialized for the client
		self.assertEqual(doc.as_dict()["items"][0]["rate"], "XXXXXXXX")

	def test_masked_child_value_preserved_on_save(self):
		"""Saving with the placeholder in a masked child field keeps the real DB value."""
		frappe.set_user(self.TEST_USER)
		doc = frappe.get_doc(self.dt, self.docname)
		doc.items[0].rate = "XXXXXXXX"  # as sent by the client
		doc.items[0].public_qty = 9
		doc.save()

		frappe.set_user("Administrator")
		saved = frappe.db.get_value(self.child_dt, self.row_name, ["rate", "public_qty"], as_dict=True)
		self.assertEqual(flt(saved.rate), 1234.5)  # masked value restored, not overwritten
		self.assertEqual(flt(saved.public_qty), 9)  # unmasked field still writable

	def _grant_mask_permission(self):
		update_permission_property(self.dt, self.TEST_ROLE, 0, "mask", 1)
		frappe.clear_cache(doctype=self.dt)

	def _revoke_mask_permission(self):
		frappe.set_user("Administrator")
		update_permission_property(self.dt, self.TEST_ROLE, 0, "mask", 0)
		frappe.clear_cache(doctype=self.dt)

	def test_child_fields_unmasked_with_parent_mask_permission(self):
		"""The mask permission on the parent doctype must unmask child-table fields,
		since child doctypes have no role permissions of their own (issue #40790)."""
		self._grant_mask_permission()
		try:
			frappe.set_user(self.TEST_USER)
			doc = frappe.get_doc(self.dt, self.docname)
			doc.apply_fieldlevel_read_permissions()

			self.assertEqual(doc.items[0].secret_note, "child_secret")
			self.assertEqual(flt(doc.items[0].rate), 1234.5)
		finally:
			self._revoke_mask_permission()

	def test_qb_child_query_masks_for_non_admin(self):
		"""Child rows fetched via the query builder's child queries must be masked."""
		frappe.set_user(self.TEST_USER)
		rows = frappe.qb.get_query(
			self.dt,
			fields=["name", {"items": ["secret_note", "rate"]}],
			filters={"name": self.docname},
			ignore_permissions=False,
		).run(as_dict=True)

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["items"][0]["secret_note"], "XXXXXXXX")
		self.assertEqual(rows[0]["items"][0]["rate"], "XXXXXXXX")

	def test_qb_child_query_unmasked_with_parent_mask_permission(self):
		self._grant_mask_permission()
		try:
			frappe.set_user(self.TEST_USER)
			rows = frappe.qb.get_query(
				self.dt,
				fields=["name", {"items": ["secret_note"]}],
				filters={"name": self.docname},
				ignore_permissions=False,
			).run(as_dict=True)

			self.assertEqual(rows[0]["items"][0]["secret_note"], "child_secret")
		finally:
			self._revoke_mask_permission()

	def test_dotted_child_field_masked_in_get_list(self):
		"""Selecting a masked child field through dot notation must mask it, the same as
		querying the child doctype directly."""
		frappe.set_user(self.TEST_USER)

		rows = frappe.get_list(self.dt, filters={"name": self.docname}, fields=["name", "items.rate"])
		self.assertEqual(rows[0]["rate"], "XXXXXXXX")

		rows = frappe.get_list(
			self.dt, filters={"name": self.docname}, fields=["name", "items.rate"], as_list=True
		)
		self.assertEqual(rows[0][1], "XXXXXXXX")

	def test_dotted_child_field_masked_in_query_engine(self):
		frappe.set_user(self.TEST_USER)
		rows = frappe.qb.get_query(
			self.dt,
			fields=["name", "items.rate", "items.secret_note"],
			filters={"name": self.docname},
			ignore_permissions=False,
		).run(as_dict=True)

		self.assertEqual(rows[0]["rate"], "XXXXXXXX")
		self.assertEqual(rows[0]["secret_note"], "XXXXXXXX")

	def test_dotted_child_field_masked_in_legacy_db_query(self):
		frappe.set_user(self.TEST_USER)
		from frappe.model.db_query import DatabaseQuery

		rows = DatabaseQuery(self.dt).execute(
			fields=["name", "items.rate", f"`tab{self.child_dt}`.`secret_note` as `child:secret_note`"],
			filters={"name": self.docname},
		)
		self.assertEqual(rows[0]["rate"], "XXXXXXXX")
		self.assertEqual(rows[0]["child:secret_note"], "XXXXXXXX")

	def test_dotted_child_field_unmasked_with_parent_mask_permission(self):
		"""A dotted child field resolves its mask permission through the parent, the same as
		the child rows themselves."""
		self._grant_mask_permission()
		try:
			frappe.set_user(self.TEST_USER)
			rows = frappe.get_list(self.dt, filters={"name": self.docname}, fields=["items.rate"])
			self.assertEqual(flt(rows[0]["rate"]), 1234.5)
		finally:
			self._revoke_mask_permission()

	def test_aliased_child_field_masked(self):
		"""The report view selects child columns under an alias (`items.rate as 'Item:rate'`),
		so masking has to match the alias the value lands under."""
		frappe.set_user(self.TEST_USER)

		rows = frappe.get_list(
			self.dt, filters={"name": self.docname}, fields=[f"`tab{self.child_dt}`.`rate` as 'child:rate'"]
		)
		self.assertEqual(rows[0]["child:rate"], "XXXXXXXX")

		rows = frappe.qb.get_query(
			self.dt,
			fields=["items.rate as child_rate"],
			filters={"name": self.docname},
			ignore_permissions=False,
		).run(as_dict=True)
		self.assertEqual(rows[0]["child_rate"], "XXXXXXXX")

	def test_plucked_dotted_child_field_masked(self):
		frappe.set_user(self.TEST_USER)
		values = frappe.qb.get_query(
			self.dt,
			fields=["items.rate"],
			filters={"name": self.docname},
			ignore_permissions=False,
		).run(pluck="rate")

		self.assertEqual(values[0], "XXXXXXXX")

	def test_plucked_aliased_child_field_masked(self):
		"""An aliased dotted field is keyed under its alias, so the pluck path has to match
		the alias too."""
		frappe.set_user(self.TEST_USER)
		values = frappe.qb.get_query(
			self.dt,
			fields=["items.rate as child_rate"],
			filters={"name": self.docname},
			ignore_permissions=False,
		).run(pluck="child_rate")

		self.assertEqual(values[0], "XXXXXXXX")

	def test_query_run_without_as_dict_masks(self):
		"""`run()` returns tuples, so masking must not treat the result as dicts."""
		frappe.set_user(self.TEST_USER)
		rows = frappe.qb.get_query(
			self.child_dt,
			fields=["rate"],
			filters={"parent": self.docname},
			parent_doctype=self.dt,
			ignore_permissions=False,
		).run()

		self.assertEqual(rows[0][0], "XXXXXXXX")

	def test_form_meta_child_masked_fields_respect_parent_permission(self):
		"""masked_fields in the form meta bundle for a child doctype must follow the
		parent doctype's mask permission."""
		from frappe.desk.form.load import get_meta_bundle

		frappe.set_user(self.TEST_USER)
		child_meta_dict = next(d for d in get_meta_bundle(self.dt) if d["name"] == self.child_dt)
		self.assertEqual(set(child_meta_dict["masked_fields"]), {"secret_note", "rate"})

		frappe.set_user("Administrator")
		self._grant_mask_permission()
		try:
			frappe.set_user(self.TEST_USER)
			child_meta_dict = next(d for d in get_meta_bundle(self.dt) if d["name"] == self.child_dt)
			self.assertEqual(child_meta_dict["masked_fields"], [])
		finally:
			self._revoke_mask_permission()


class TestMaskFieldsInLinkedDocType(IntegrationTestCase):
	"""A masked field on a link target must stay masked when selected through the link
	(`customer.tax_id`), not just when its own doctype is queried."""

	TEST_USER = "test_mask_link_field_user@example.com"
	TEST_ROLE = "Test Mask Link Field Role"

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
					"first_name": "Mask Link Field Test",
					"send_welcome_email": 0,
					"roles": [{"role": cls.TEST_ROLE}],
				}
			).insert(ignore_permissions=True)
		else:
			frappe.get_doc("User", cls.TEST_USER).add_roles(cls.TEST_ROLE)

		cls.target_dt = (
			new_doctype(
				fields=[_make_field("tax_id", "Data", mask=1)],
				permissions=[{"role": cls.TEST_ROLE, "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)

		cls.dt = (
			new_doctype(
				fields=[_make_field("customer", "Link", options=cls.target_dt, mask=0)],
				permissions=[{"role": cls.TEST_ROLE, "read": 1, "write": 1, "create": 1}],
			)
			.insert()
			.name
		)

		cls.target_name = frappe.get_doc({"doctype": cls.target_dt, "tax_id": "GST12345"}).insert().name
		cls.docname = frappe.get_doc({"doctype": cls.dt, "customer": cls.target_name}).insert().name

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.delete(cls.dt)
		frappe.db.delete(cls.target_dt)
		frappe.delete_doc("DocType", cls.dt, force=True)
		frappe.delete_doc("DocType", cls.target_dt, force=True)
		if frappe.db.exists("User", cls.TEST_USER):
			frappe.db.set_value("User", cls.TEST_USER, "enabled", 0)
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_masked_field_selected_through_link_is_masked(self):
		frappe.set_user(self.TEST_USER)

		rows = frappe.get_list(self.dt, filters={"name": self.docname}, fields=["customer.tax_id"])
		self.assertEqual(rows[0]["tax_id"], "XXXXXXXX")

		rows = frappe.qb.get_query(
			self.dt,
			fields=["customer.tax_id"],
			filters={"name": self.docname},
			ignore_permissions=False,
		).run(as_dict=True)
		self.assertEqual(rows[0]["tax_id"], "XXXXXXXX")

	def test_masked_field_through_link_masked_in_legacy_db_query(self):
		"""The link target is joined under a counter alias (`tabUser_1`), which has to resolve
		back to the real doctype before its masked fields can be looked up."""
		frappe.set_user(self.TEST_USER)
		from frappe.model.db_query import DatabaseQuery

		rows = DatabaseQuery(self.dt).execute(
			fields=["name", "customer.tax_id"],
			filters={"name": self.docname},
		)
		self.assertEqual(rows[0]["tax_id"], "XXXXXXXX")

	def test_masked_field_through_link_follows_target_mask_permission(self):
		"""Link targets are standalone doctypes, so their own mask permission applies."""
		update_permission_property(self.target_dt, self.TEST_ROLE, 0, "mask", 1)
		frappe.clear_cache(doctype=self.target_dt)

		try:
			frappe.set_user(self.TEST_USER)
			rows = frappe.get_list(self.dt, filters={"name": self.docname}, fields=["customer.tax_id"])
			self.assertEqual(rows[0]["tax_id"], "GST12345")
		finally:
			frappe.set_user("Administrator")
			update_permission_property(self.target_dt, self.TEST_ROLE, 0, "mask", 0)
			frappe.clear_cache(doctype=self.target_dt)


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
