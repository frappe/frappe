# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

PAGE_SIZE = 20


class DocumentTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		data: DF.Code
		disabled: DF.Check
		private: DF.Check
		reference_doctype: DF.Link
		template_name: DF.Data
	# end: auto-generated types

	def validate(self) -> None:
		self._validate_template_data_json()
		self._validate_duplicate_name()

	def _validate_duplicate_name(self) -> None:
		"""Prevent duplicate template names within the same reference doctype.

		Rules:
		  - Two public templates with the same name for the same doctype: blocked.
		  - Two private templates with the same name by the same owner: blocked.
		  - Private templates of different owners may share a name.
		  - A user may have one public and one private template with the same name.
		"""
		if self.private:
			# Private: only block if the same owner already has a private template with this name
			conflict = frappe.db.exists(
				"Document Template",
				{
					"reference_doctype": self.reference_doctype,
					"template_name": self.template_name,
					"owner": self.owner,
					"private": 1,
					"name": ("!=", self.name),
				},
			)
		else:
			# Public: block if another public template has this name
			conflict = frappe.db.exists(
				"Document Template",
				{
					"reference_doctype": self.reference_doctype,
					"template_name": self.template_name,
					"name": ("!=", self.name),
					"private": 0,
				},
			)

		if conflict:
			frappe.throw(
				_("A template named {0} already exists for {1}").format(
					frappe.bold(self.template_name),
					frappe.bold(self.reference_doctype),
				)
			)

	def _validate_template_data_json(self) -> None:
		"""Ensure that the 'data' field contains valid, non-empty JSON object data."""
		try:
			parsed_data = json.loads(self.data)
		except (json.JSONDecodeError, TypeError, ValueError):
			frappe.throw(_("Template data must be valid JSON"))

		if not isinstance(parsed_data, dict):
			frappe.throw(_("Template data must be a JSON object"))

		if not parsed_data:
			frappe.throw(_("Template data cannot be empty"))


@frappe.whitelist()
def get_templates(reference_doctype: str, page: int = 1) -> dict:
	"""Return templates for the manage dialog, filtered and sorted server-side.

	Sorting order: ``disabled asc, private desc, name asc``
	  - Active templates come first (private before public, then alphabetical).
	  - Disabled templates fall naturally to the last page(s).

	Returns::
	    {
	        "templates": [...],  # paginated slice (active first, disabled at end)
	        "has_next_page": bool,
	        "total": int,
	    }
	"""
	user = frappe.session.user
	is_admin = _is_system_manager(user)

	all_templates = frappe.get_all(
		"Document Template",
		filters={"reference_doctype": reference_doctype},
		fields=["name", "template_name", "owner", "private", "disabled", "data"],
		order_by="disabled asc, private desc, name asc",
		ignore_permissions=True,
	)

	visible: list[dict] = []
	for t in all_templates:
		if _is_visible(t, user, is_admin, reference_doctype):
			t.pop("data", None)
			visible.append(t)

	page = max(1, int(page))
	start = (page - 1) * PAGE_SIZE
	end = start + PAGE_SIZE

	return {
		"templates": visible[start:end],
		"has_next_page": end < len(visible),
		"total": len(visible),
	}


@frappe.whitelist()
def get_template_data(name: str) -> str:
	"""Return the ``data`` field for a single template.

	Fetches with ``ignore_permissions=True`` so the row-level SQL filter
	(``get_permission_query_conditions``) does not block the lookup, then
	performs an explicit ``has_permission`` check before returning the value.
	"""
	row = frappe.db.get_value(
		"Document Template",
		name,
		["name", "data", "private", "owner", "disabled", "reference_doctype"],
		as_dict=True,
	)

	user = frappe.session.user
	if not has_permission(frappe._dict(row), "read", user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not row:
		frappe.throw(_("Template {0} not found").format(name), frappe.DoesNotExistError)

	return row.data


def _is_visible(template: dict, user: str, is_admin: bool, reference_doctype: str) -> bool:
	"""Return True if *template* should appear in the listing for *user*."""
	is_owner = template.owner == user

	if template.disabled:
		return is_admin or is_owner

	if is_admin or is_owner:
		return True

	if not template.private:
		return _check_user_permissions_on_template_data(template.data, reference_doctype, user)

	return False


def _check_user_permissions_on_template_data(template_data: str, reference_doctype: str, user: str) -> bool:
	"""Check if the template's stored field values comply with the user's User Permissions.

	For every link field on *reference_doctype* where the user has User Permission
	restrictions, the value stored inside the template JSON must be in the
	allowed set (or empty, unless strict user permissions are enabled).
	"""
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions

	user_permissions = get_user_permissions(user)
	if not user_permissions:
		return True

	try:
		data = json.loads(template_data) if isinstance(template_data, str) else template_data
	except (json.JSONDecodeError, TypeError, ValueError):
		return True

	if not isinstance(data, dict):
		return True

	apply_strict = frappe.get_system_settings("apply_strict_user_permissions")
	meta = frappe.get_meta(reference_doctype)

	for field in meta.get_link_fields():
		if field.ignore_user_permissions:
			continue

		if field.options not in user_permissions:
			continue

		value = data.get(field.fieldname)

		if not value and not apply_strict:
			continue

		allowed_docs = frappe.permissions.get_allowed_docs_for_doctype(
			user_permissions.get(field.options, []), reference_doctype
		)

		if allowed_docs and str(value or "") not in allowed_docs:
			return False

	return True


def _is_system_manager(user: str) -> bool:
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Row-level SQL filter for get_list / get_all queries.

	System Manager / Administrator see everything.
	Others see nothing
	"""
	if not user:
		user = frappe.session.user

	if _is_system_manager(user):
		return ""

	return "1=0"


def has_permission(doc: "DocumentTemplate", ptype: str, user: str | None = None) -> bool:
	"""Doc-level permission check.

	Rules:
	  1. System Manager / Administrator — all operations allowed.
	  2. Owner — all operations allowed on own templates.
	  3. Others (must be able to create the reference doctype):
	     - create: allowed
	     - read/select public templates: allowed (subject to user permission check on data)
	     - write / delete any template: denied (owner + System Manager only)
	     - read private templates: denied (owner + System Manager only)
	"""
	if not user:
		user = frappe.session.user

	if _is_system_manager(user):
		return True

	if user == doc.owner:
		return True

	if not frappe.has_permission(doc.reference_doctype, "create", user=user):
		return False

	if ptype == "create":
		return True

	if not doc.private and ptype in ("read", "select"):
		template_data = getattr(doc, "data", None)
		if template_data and not _check_user_permissions_on_template_data(
			template_data, doc.reference_doctype, user
		):
			return False
		return True

	return False
