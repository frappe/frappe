# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import orjson

import frappe
from frappe import _
from frappe.model.document import Document


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

	def before_save(self) -> None:
		"""Pretty-print and sort the template data JSON before persisting."""
		try:
			parsed = orjson.loads(self.data)
		except (orjson.JSONDecodeError, TypeError, ValueError):
			return
		if isinstance(parsed, dict):
			self.data = frappe.as_json(parsed, indent=1)

	def _validate_duplicate_name(self) -> None:
		"""Prevent duplicate template names within the same reference doctype.

		Rules:
		  - Two public templates with the same name for the same doctype: blocked.
		  - Two private templates with the same name by the same owner: blocked.
		  - Private templates of different owners may share a name.
		  - A user may have one public and one private template with the same name.
		"""
		if self.private:
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
			if conflict:
				frappe.throw(
					_("A private template named {0} already exists for {1}").format(
						frappe.bold(self.template_name),
						frappe.bold(self.reference_doctype),
					)
				)
		else:
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
					_("A public template named {0} already exists for {1}").format(
						frappe.bold(self.template_name),
						frappe.bold(self.reference_doctype),
					)
				)

	def _validate_template_data_json(self) -> None:
		"""Ensure that the 'data' field contains valid, non-empty JSON object data."""
		try:
			parsed_data = orjson.loads(self.data)
		except (orjson.JSONDecodeError, TypeError, ValueError):
			frappe.throw(_("Template data must be valid JSON"))

		if not isinstance(parsed_data, dict):
			frappe.throw(_("Template data must be a JSON object"))

		if not parsed_data:
			frappe.throw(_("Template data cannot be empty"))


@frappe.whitelist()
def get_templates(reference_doctype: str, limit_start: int = 0, limit_page_length: int = 10) -> dict:
	"""Return templates for the manage dialog, filtered and sorted server-side.

	Sorting: ``disabled asc, private desc, template_name asc``

	Returns::

	    {"templates": [...], "has_next_page": bool, "total": int}
	"""
	user = frappe.session.user

	all_templates = frappe.get_all(
		"Document Template",
		filters={"reference_doctype": reference_doctype},
		fields=["name", "template_name", "owner", "private", "disabled", "data", "reference_doctype"],
		order_by="disabled asc, private desc, template_name asc",
		ignore_permissions=True,
	)

	visible: list[dict] = []
	for t in all_templates:
		if has_permission(frappe._dict(t), "read", user) and (
			not t.get("disabled") or t.get("owner") == user
		):
			visible.append(t)
			t.pop("data", None)

	start = max(0, int(limit_start))
	length = max(1, int(limit_page_length))
	end = start + length

	return {
		"templates": visible[start:end],
		"has_next_page": end < len(visible),
		"total": len(visible),
	}


@frappe.whitelist()
def get_template_data(name: str) -> str:
	"""Return the ``data`` field for a single template.

	Fetches with ``ignore_permissions=True`` then performs an explicit
	``has_permission`` check so the row-level SQL filter does not block.
	"""
	row = frappe.db.get_value(
		"Document Template",
		name,
		["name", "data", "private", "owner", "disabled", "reference_doctype"],
		as_dict=True,
	)

	if not row:
		frappe.throw(_("Template {0} not found").format(name), frappe.DoesNotExistError)

	user = frappe.session.user
	if not has_permission(frappe._dict(row), "read", user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	return row.data


def _check_user_permissions_on_template_data(template_data: str, reference_doctype: str, user: str) -> bool:
	"""Build a temporary doc from template JSON and delegate to
	``frappe.permissions.has_user_permission`` for link-field checks."""
	data = orjson.loads(template_data)

	try:
		temp_doc = frappe.new_doc(reference_doctype)
		temp_doc.update(data)
		return frappe.permissions.has_user_permission(temp_doc, user=user)
	except Exception:
		return False


def _is_system_manager(user: str) -> bool:
	return "System Manager" in frappe.get_roles(user)


def _has_template_manager_role(user: str) -> bool:
	return "Template Manager" in frappe.get_roles(user)


def _get_creatable_doctypes(user: str) -> list[str]:
	"""Return list of doctypes *user* can create."""
	from frappe.utils.user import UserPermissions

	user_perms = UserPermissions(user)
	user_perms.build_permissions()
	return user_perms.can_create or []


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Row-level SQL filter for ``get_list`` / ``get_all``.

	- **System Manager** — sees everything.
	- **Template Manager** — public templates and own private templates,
	  scoped to doctypes they can create.
	- **Everyone else** — ``1=0`` (desk users use the form dialog API).
	"""
	if not user:
		user = frappe.session.user

	if _is_system_manager(user):
		return ""

	if _has_template_manager_role(user):
		creatable = _get_creatable_doctypes(user)
		if not creatable:
			return "1=0"
		doctype_list = ", ".join(frappe.db.escape(dt) for dt in creatable)
		return (
			f"`tabDocument Template`.`reference_doctype` IN ({doctype_list})"
			f" AND (`tabDocument Template`.`private` = 0 OR `tabDocument Template`.`owner` = {frappe.db.escape(user)})"
		)

	return "1=0"


def has_permission(doc, ptype="read", user=None) -> bool:
	"""Doc-level permission check.

	Permission levels:

	1. **System Manager** — all operations allowed.
	2. **Owner** — all operations on own templates.
	3. **Template Manager** — read/write/delete public templates and
	   own private templates, scoped to doctypes they can create.
	4. **Desk Users** — create if they can create the reference doctype;
	   read/select public templates (subject to user permission checks);
	   no write/delete on others' templates.
	"""
	if not user:
		user = frappe.session.user

	if _is_system_manager(user):
		return True

	if user == doc.owner:
		return True

	if _has_template_manager_role(user):
		if not frappe.has_permission(doc.reference_doctype, ptype="create", user=user):
			return False
		return not doc.private or user == doc.owner

	if frappe.has_permission(doc.reference_doctype, ptype="create", user=user) and ptype == "create":
		return True

	if not doc.private and ptype in ("read", "select"):
		template_data = getattr(doc, "data", None)
		if template_data and not _check_user_permissions_on_template_data(
			template_data, doc.reference_doctype, user
		):
			return False
		return True

	return False
