# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt
"""Comprehensive tests for the Document Template doctype.

Covers:

* validation rules (data shape, duplicate naming, private→public conversion)
* the whitelisted ``get_templates`` API used by the form toolbar
* row-level ``get_permission_query_conditions`` used by list view / get_list
* doc-level ``has_permission`` used by the rest of the framework
* user-permission filtering on a template's payload
"""

from __future__ import annotations

import json

import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.desk.doctype.document_template.document_template import (
	_has_user_permissions_on_template_data,
	get_permission_query_conditions,
	get_templates,
	has_permission,
)
from frappe.permissions import (
	add_user_permission,
	clear_user_permissions_for_doctype,
)
from frappe.tests import IntegrationTestCase

REF_DOCTYPE = "ToDo"
ADMIN_ONLY_DOCTYPE = "User"  # Desk users cannot create User docs.

TEMPLATE_MANAGER_ROLE = "_Test DT Template Manager"


def _delete_test_templates():
	"""Remove Document Template rows whose names start with the test prefix."""
	frappe.db.delete("Document Template", {"template_name": ("like", "_Test %")})


def _make_data(**values) -> str:
	"""Return a JSON ``data`` payload for a ``ToDo`` template."""
	values.setdefault("description", "Sample description")
	return json.dumps(values)


def _ensure_template_manager_role():
	"""Create a custom role with full write access on Document Template (no if_owner)."""
	if not frappe.db.exists("Role", TEMPLATE_MANAGER_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": TEMPLATE_MANAGER_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)

	from frappe.permissions import setup_custom_perms

	setup_custom_perms("Document Template")
	if not frappe.db.exists(
		"Custom DocPerm",
		{"parent": "Document Template", "role": TEMPLATE_MANAGER_ROLE, "permlevel": 0},
	):
		frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": "Document Template",
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": TEMPLATE_MANAGER_ROLE,
				"permlevel": 0,
				"if_owner": 0,
				"read": 1,
				"write": 1,
				"create": 1,
				"delete": 1,
			}
		).insert(ignore_permissions=True)
	frappe.clear_cache()


def _drop_template_manager_role():
	frappe.db.delete(
		"Custom DocPerm",
		{"parent": "Document Template", "role": TEMPLATE_MANAGER_ROLE},
	)
	if frappe.db.exists("Role", TEMPLATE_MANAGER_ROLE):
		frappe.delete_doc("Role", TEMPLATE_MANAGER_ROLE, force=True, ignore_permissions=True)
	frappe.clear_cache()


class TestDocumentTemplate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_template_manager_role()
		_delete_test_templates()
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		_drop_template_manager_role()
		_delete_test_templates()
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def tearDown(self):
		frappe.set_user("Administrator")
		_delete_test_templates()
		frappe.db.commit()  # nosemgrep
		super().tearDown()

	def _make_template(
		self,
		template_name: str,
		*,
		reference_doctype: str = REF_DOCTYPE,
		private: int = 0,
		disabled: int = 0,
		data: str | None = None,
		owner: str | None = None,
	):
		"""Insert a Document Template, optionally as ``owner``."""
		previous_user = frappe.session.user
		try:
			if owner:
				frappe.set_user(owner)
			doc = frappe.get_doc(
				{
					"doctype": "Document Template",
					"template_name": f"_Test {template_name}",
					"reference_doctype": reference_doctype,
					"private": private,
					"disabled": disabled,
					"data": data or _make_data(description=template_name),
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.set_user(previous_user)
		return doc

	def test_invalid_json_payload_rejected(self):
		for payload in ("[]", "[1, 2, 3]", '"a string"', "12", "null", {}):
			with self.subTest(payload=payload):
				with self.assertRaises(frappe.ValidationError):
					frappe.get_doc(
						{
							"doctype": "Document Template",
							"template_name": f"bad-{payload}",
							"reference_doctype": REF_DOCTYPE,
							"data": payload,
						}
					).insert(ignore_permissions=True)

	def test_data_is_pretty_printed_on_save(self):
		raw = '{"description":"hello","priority":"High"}'
		t = self._make_template("normalised", data=raw)
		self.assertIn("\n", t.data)
		self.assertEqual(json.loads(t.data), {"description": "hello", "priority": "High"})

	def test_duplicate_public_template_blocked(self):
		self._make_template("dup-public")
		with self.assertRaises(frappe.ValidationError):
			self._make_template("dup-public")

	def test_duplicate_public_template_blocked_across_different_owners(self):
		with test_user(roles=["System Manager"]) as user_a, test_user(roles=["System Manager"]) as user_b:
			self._make_template("shared-public", owner=user_a.name)
			with self.assertRaises(frappe.ValidationError):
				self._make_template("shared-public", owner=user_b.name)

	def test_duplicate_private_same_owner_blocked(self):
		with test_user(roles=["System Manager"]) as user:
			self._make_template("priv", private=1, owner=user.name)
			with self.assertRaises(frappe.ValidationError):
				self._make_template("priv", private=1, owner=user.name)

	def test_duplicate_private_different_owners_allowed(self):
		with test_user(roles=["System Manager"]) as u1, test_user(roles=["System Manager"]) as u2:
			self._make_template("priv-shared", private=1, owner=u1.name)
			self._make_template("priv-shared", private=1, owner=u2.name)

	def test_user_can_have_public_and_private_with_same_name(self):
		with test_user(roles=["System Manager"]) as user:
			self._make_template("mix", private=0, owner=user.name)
			self._make_template("mix", private=1, owner=user.name)

	def test_duplicate_check_scoped_to_reference_doctype(self):
		"""Templates with the same name for *different* reference doctypes are fine."""
		self._make_template("scoped")
		t2 = self._make_template(
			"scoped", reference_doctype=ADMIN_ONLY_DOCTYPE, data=json.dumps({"first_name": "x"})
		)
		self.assertTrue(frappe.db.exists("Document Template", t2.name))

	def test_public_template_does_not_collide_with_existing_private_of_same_name(self):
		"""A public template with the same name as someone's private template is allowed."""
		with test_user(roles=["System Manager"]) as user:
			self._make_template("collide-name", private=1, owner=user.name)
			self._make_template("collide-name", private=0)

	def test_only_owner_can_make_template_public(self):
		with test_user(roles=["System Manager"]) as owner_user:
			t = self._make_template("convert-me", private=1, owner=owner_user.name)

		t.reload()
		t.private = 0
		with self.assertRaises(frappe.ValidationError):
			t.save(ignore_permissions=True)

	def test_owner_can_make_template_public(self):
		with test_user(roles=["System Manager"]) as owner_user:
			t = self._make_template("self-convert", private=1, owner=owner_user.name)
			frappe.set_user(owner_user.name)
			t.reload()
			t.private = 0
			t.save(ignore_permissions=True)
			t.reload()
			self.assertEqual(t.private, 0)

	def test_changing_unrelated_fields_as_non_owner_does_not_trigger_conversion_check(self):
		with test_user(roles=["System Manager"]) as owner_user:
			t = self._make_template("untouched-private", private=1, owner=owner_user.name)

		t.reload()
		t.disabled = 1
		t.save(ignore_permissions=True)
		t.reload()
		self.assertEqual(t.private, 1)
		self.assertEqual(t.disabled, 1)

	def test_get_templates_requires_create_on_reference_doctype(self):
		with test_user(roles=["Desk User"]) as user, self.set_user(user.name):
			with self.assertRaises(frappe.PermissionError):
				get_templates(reference_doctype=ADMIN_ONLY_DOCTYPE)

	def test_get_templates_requires_read_on_document_template(self):
		with self.set_user("Guest"):
			with self.assertRaises(frappe.PermissionError):
				get_templates(reference_doctype=REF_DOCTYPE)

	def test_get_templates_returns_public_and_own_private_only(self):
		with test_user(roles=["Desk User"]) as user_a, test_user(roles=["Desk User"]) as user_b:
			self._make_template("public", private=0)
			self._make_template("a-private", private=1, owner=user_a.name)
			self._make_template("b-private", private=1, owner=user_b.name)

			with self.set_user(user_a.name):
				result = get_templates(reference_doctype=REF_DOCTYPE)

		names = [t.template_name for t in result["templates"]]
		self.assertIn("_Test public", names)
		self.assertIn("_Test a-private", names)
		self.assertNotIn("_Test b-private", names)

	def test_get_templates_disabled_visible_only_to_owner(self):
		with test_user(roles=["Desk User"]) as owner_user, test_user(roles=["Desk User"]) as other:
			self._make_template("dis-public", private=0, disabled=1, owner=owner_user.name)

			with self.set_user(owner_user.name):
				owner_view = [
					t.template_name for t in get_templates(reference_doctype=REF_DOCTYPE)["templates"]
				]

			with self.set_user(other.name):
				other_view = [
					t.template_name for t in get_templates(reference_doctype=REF_DOCTYPE)["templates"]
				]

		self.assertIn("_Test dis-public", owner_view)
		self.assertNotIn("_Test dis-public", other_view)

	def test_get_templates_sorts_by_disabled_private_name(self):
		"""Order: enabled before disabled, private before public, name asc."""
		with test_user(roles=["Desk User"]) as user:
			self._make_template("zzz-public", private=0, owner=user.name)
			self._make_template("aaa-public", private=0, owner=user.name)
			self._make_template("priv-bbb", private=1, owner=user.name)
			self._make_template("priv-aaa", private=1, owner=user.name)
			self._make_template("disabled-x", private=0, disabled=1, owner=user.name)

			with self.set_user(user.name):
				ordered = [
					t.template_name
					for t in get_templates(reference_doctype=REF_DOCTYPE, limit_page_length=50)["templates"]
					if t.template_name.startswith("_Test ")
				]

		self.assertEqual(
			ordered,
			["_Test priv-aaa", "_Test priv-bbb", "_Test aaa-public", "_Test zzz-public", "_Test disabled-x"],
		)

	def test_get_templates_pagination_and_has_next_flag(self):
		with test_user(roles=["Desk User"]) as user:
			for i in range(7):
				self._make_template(f"t-{i:02d}", private=1, owner=user.name)

			with self.set_user(user.name):
				page1 = get_templates(reference_doctype=REF_DOCTYPE, limit_start=0, limit_page_length=3)
				page2 = get_templates(reference_doctype=REF_DOCTYPE, limit_start=3, limit_page_length=3)
				page3 = get_templates(reference_doctype=REF_DOCTYPE, limit_start=6, limit_page_length=3)

		# Count only _Test t-XX templates owned by this user
		self.assertEqual(len([t for t in page1["templates"] if t.template_name.startswith("_Test t-")]), 3)
		self.assertTrue(page1["has_next_page"])
		self.assertEqual(len([t for t in page2["templates"] if t.template_name.startswith("_Test t-")]), 3)
		self.assertTrue(page2["has_next_page"])
		self.assertEqual(len([t for t in page3["templates"] if t.template_name.startswith("_Test t-")]), 1)
		self.assertFalse(page3["has_next_page"])

	def test_get_templates_strips_data_payload_from_response(self):
		self._make_template("with-data", data=_make_data(description="secret"))
		with test_user(roles=["Desk User"]) as user, self.set_user(user.name):
			result = get_templates(reference_doctype=REF_DOCTYPE)
		self.assertTrue(result["templates"])
		for t in result["templates"]:
			self.assertNotIn("data", t)

	def test_get_templates_filters_via_user_permission_check_hook(self):
		"""``get_templates`` excludes templates whose payload contains a link value
		the requesting user is not permitted to access via User Permissions.

		We create two templates: one referencing a Role the user *is* allowed to
		see, one referencing a Role they are *not* allowed to see.  Only the
		permitted template should appear in the result.
		"""
		with test_user(roles=["Desk User"]) as user:
			# Restrict the user so they can only see the "Desk User" Role.
			add_user_permission("Role", "Desk User", user.name, ignore_permissions=True)
			try:
				# ToDo has a `role` Link field - use it as the restricted link.
				allowed = self._make_template(
					"perm-allowed",
					data=_make_data(description="allowed", role="Desk User"),
				)
				blocked = self._make_template(
					"perm-blocked",
					data=_make_data(description="blocked", role="System Manager"),
				)

				with self.set_user(user.name):
					names = [
						t.template_name for t in get_templates(reference_doctype=REF_DOCTYPE)["templates"]
					]
			finally:
				clear_user_permissions_for_doctype("Role", user.name)

		self.assertIn(allowed.template_name, names)
		self.assertNotIn(blocked.template_name, names)

	def test_get_templates_system_manager_sees_all_public_and_own_private_only(self):
		"""System Manager sees all public and own private template in the list view."""
		with (
			test_user(roles=["Desk User"]) as owner_user,
			test_user(roles=["System Manager"]) as sm,
		):
			pub = self._make_template("sm-public", private=0, owner=owner_user.name)
			priv = self._make_template("sm-private", private=1, owner=owner_user.name)

			with self.set_user(sm.name):
				names = [t.template_name for t in get_templates(reference_doctype=REF_DOCTYPE)["templates"]]

		self.assertIn(pub.template_name, names)
		self.assertNotIn(priv.template_name, names)

	def test_get_templates_template_manager_sees_public_and_own_private_only(self):
		"""Template Manager sees public templates and their own private ones,
		but not private templates owned by others."""
		with (
			test_user(roles=[TEMPLATE_MANAGER_ROLE, "Desk User"]) as manager,
			test_user(roles=["System Manager"]) as other,
		):
			pub = self._make_template("tm-pub", private=0, owner=other.name)
			own_priv = self._make_template("tm-own-priv", private=1, owner=manager.name)
			other_priv = self._make_template("tm-other-priv", private=1, owner=other.name)

			with self.set_user(manager.name):
				names = [t.template_name for t in get_templates(reference_doctype=REF_DOCTYPE)["templates"]]

		self.assertIn(pub.template_name, names)
		self.assertIn(own_priv.template_name, names)
		self.assertNotIn(other_priv.template_name, names)

	def test_get_templates_template_manager_without_create_on_ref_doctype_is_denied(self):
		"""Template Manager role is not enough on its own — the user must also have
		'create' permission on the reference doctype.  Without it ``get_templates``
		should raise ``PermissionError``."""
		with test_user(roles=[TEMPLATE_MANAGER_ROLE, "Desk User"]) as manager:
			with self.set_user(manager.name):
				with self.assertRaises(frappe.PermissionError):
					get_templates(reference_doctype=ADMIN_ONLY_DOCTYPE)

	def test_get_templates_clamps_negative_limit_start(self):
		self._make_template("clamp-test")
		with test_user(roles=["Desk User"]) as user, self.set_user(user.name):
			result = get_templates(reference_doctype=REF_DOCTYPE, limit_start=-10, limit_page_length=5)
		self.assertEqual(len([t for t in result["templates"] if t.template_name.startswith("_Test ")]), 1)

	def test_get_templates_clamps_zero_page_length(self):
		"""``limit_page_length<=0`` is normalised to 1."""
		for i in range(3):
			self._make_template(f"clamp-len-{i}")
		with test_user(roles=["Desk User"]) as user, self.set_user(user.name):
			result = get_templates(reference_doctype=REF_DOCTYPE, limit_page_length=0)
		self.assertEqual(len(result["templates"]), 1)
		self.assertTrue(result["has_next_page"])

	def test_has_user_permissions_returns_true_when_no_user_permissions(self):
		data = _make_data(description="hello")
		self.assertTrue(_has_user_permissions_on_template_data(data, REF_DOCTYPE, "Administrator"))

	def test_has_user_permissions_blocks_when_link_value_disallowed(self):
		"""A link value the user can't access should make the check fail."""
		with test_user(roles=["Desk User"]) as user:
			add_user_permission("Role", "Desk User", user.name, ignore_permissions=True)
			try:
				ok = _has_user_permissions_on_template_data(
					_make_data(description="x", role="Desk User"),
					REF_DOCTYPE,
					user.name,
				)
				blocked = _has_user_permissions_on_template_data(
					_make_data(description="x", role="System Manager"),
					REF_DOCTYPE,
					user.name,
				)
			finally:
				clear_user_permissions_for_doctype("Role", user.name)
		self.assertTrue(ok)
		self.assertFalse(blocked)

	def test_query_conditions_for_user_without_write_without_owner(self):
		"""Plain Desk User has write only via if_owner — gets blocked at query level."""
		with test_user(roles=["Desk User"]) as user:
			cond = get_permission_query_conditions(user.name)
		self.assertEqual(cond, "1=0")

	def test_query_conditions_for_user_with_no_creatable_doctypes(self):
		cond = get_permission_query_conditions("Guest")
		self.assertEqual(cond, "1=0")

	def test_query_conditions_for_system_manager_has_no_private_filter(self):
		with test_user(roles=["System Manager"]) as user:
			cond = get_permission_query_conditions(user.name)
		self.assertNotEqual(cond, "1=0")
		self.assertIn("reference_doctype", cond)
		self.assertNotIn("private", cond)

	def test_query_conditions_for_template_manager_has_private_filter(self):
		"""A non-System-Manager role with write w/o if_owner gets a private filter."""
		with test_user(roles=[TEMPLATE_MANAGER_ROLE, "Desk User"]) as user:
			cond = get_permission_query_conditions(user.name)

		self.assertNotEqual(cond, "1=0")
		self.assertIn("private", cond)
		self.assertIn("owner", cond)
		self.assertIn(frappe.db.escape(user.name), cond)

	def test_query_conditions_default_user_falls_back_to_session_user(self):
		"""Calling without arguments uses ``frappe.session.user``."""
		frappe.set_user("Administrator")
		cond_default = get_permission_query_conditions()
		cond_explicit = get_permission_query_conditions("Administrator")
		self.assertEqual(cond_default, cond_explicit)

	def test_list_view_is_empty_for_normal_desk_user(self):
		self._make_template("listview-public")
		with test_user(roles=["Desk User"]) as user, self.set_user(user.name):
			rows = frappe.get_list("Document Template", filters={"reference_doctype": REF_DOCTYPE})
		self.assertEqual(rows, [])

	def test_list_view_returns_rows_for_system_manager(self):
		t = self._make_template("listview-sm")
		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			names = [
				r.name
				for r in frappe.get_list("Document Template", filters={"reference_doctype": REF_DOCTYPE})
			]
		self.assertIn(t.name, names)

	def test_list_view_for_template_manager_excludes_others_private(self):
		with (
			test_user(roles=[TEMPLATE_MANAGER_ROLE, "Desk User"]) as manager,
			test_user(roles=["System Manager"]) as other,
		):
			pub = self._make_template("tm-pub", private=0)
			own_priv = self._make_template("tm-own-priv", private=1, owner=manager.name)
			other_priv = self._make_template("tm-other-priv", private=1, owner=other.name)

			with self.set_user(manager.name):
				names = {
					r.name
					for r in frappe.get_list("Document Template", filters={"reference_doctype": REF_DOCTYPE})
				}

		self.assertIn(pub.name, names)
		self.assertIn(own_priv.name, names)
		self.assertNotIn(other_priv.name, names)

	def test_has_permission_denied_when_no_create_on_reference_doctype(self):
		t = self._make_template(
			"perm-noref", reference_doctype=ADMIN_ONLY_DOCTYPE, data=json.dumps({"first_name": "x"})
		)
		with test_user(roles=["Desk User"]) as user:
			self.assertFalse(has_permission(t, user=user.name, ptype="read"))

	def test_has_permission_template_manager_without_create_on_ref_doctype_is_denied(self):
		"""``has_permission`` must return ``False`` for a Template Manager when they
		lack 'create' on the reference doctype"""
		t = self._make_template(
			"perm-tm-noref",
			reference_doctype=ADMIN_ONLY_DOCTYPE,
			data=json.dumps({"first_name": "x"}),
		)
		with test_user(roles=[TEMPLATE_MANAGER_ROLE, "Desk User"]) as manager:
			for ptype in ("read", "write", "delete", "create"):
				with self.subTest(ptype=ptype):
					self.assertFalse(has_permission(t, user=manager.name, ptype=ptype))

	def test_has_permission_create_allowed_with_ref_create_perm(self):
		t = self._make_template("perm-create")
		with test_user(roles=["Desk User"]) as user:
			self.assertTrue(has_permission(t, user=user.name, ptype="create"))

	def test_has_permission_owner_full_access(self):
		with test_user(roles=["Desk User"]) as user:
			t = self._make_template("perm-own", private=1, owner=user.name)
			for ptype in ("read", "write", "delete"):
				with self.subTest(ptype=ptype):
					self.assertTrue(has_permission(t, user=user.name, ptype=ptype))

	def test_has_permission_other_user_cannot_access_private(self):
		with test_user(roles=["Desk User"]) as owner_user, test_user(roles=["Desk User"]) as other:
			t = self._make_template("perm-priv", private=1, owner=owner_user.name)
			self.assertFalse(has_permission(t, user=other.name, ptype="read"))
			self.assertFalse(has_permission(t, user=other.name, ptype="write"))

	def test_has_permission_system_manager_can_access_others_private(self):
		with test_user(roles=["Desk User"]) as owner_user, test_user(roles=["System Manager"]) as sm:
			t = self._make_template("perm-priv-sm", private=1, owner=owner_user.name)
			self.assertTrue(has_permission(t, user=sm.name, ptype="read"))
			self.assertTrue(has_permission(t, user=sm.name, ptype="write"))

	def test_has_permission_template_manager_cannot_access_others_private(self):
		"""Even Template Manager (write w/o owner) cannot see private templates of others."""
		with (
			test_user(roles=["Desk User"]) as owner_user,
			test_user(roles=[TEMPLATE_MANAGER_ROLE, "Desk User"]) as manager,
		):
			t = self._make_template("perm-priv-tm", private=1, owner=owner_user.name)
			self.assertFalse(has_permission(t, user=manager.name, ptype="read"))
			self.assertFalse(has_permission(t, user=manager.name, ptype="delete"))

	def test_has_permission_other_user_can_read_public(self):
		with test_user(roles=["Desk User"]) as owner_user, test_user(roles=["Desk User"]) as other:
			t = self._make_template("perm-pub", private=0, owner=owner_user.name)
			self.assertTrue(has_permission(t, user=other.name, ptype="read"))

	def test_has_permission_blocks_when_user_permission_denies_payload(self):
		"""User-permission restrictions on payload data deny access for non-owners."""
		with test_user(roles=["Desk User"]) as owner_user, test_user(roles=["Desk User"]) as other:
			t = self._make_template(
				"perm-userperm",
				private=0,
				owner=owner_user.name,
				data=_make_data(description="x", role="System Manager"),
			)
			add_user_permission("Role", "Desk User", other.name, ignore_permissions=True)
			try:
				self.assertFalse(has_permission(t, user=other.name, ptype="read"))
			finally:
				clear_user_permissions_for_doctype("Role", other.name)
