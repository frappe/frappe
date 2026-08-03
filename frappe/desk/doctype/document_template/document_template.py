# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import orjson

import frappe
from frappe import _
from frappe.desk.form.load import getdoctype
from frappe.model.document import Document
from frappe.permissions import get_role_permissions, has_user_permission


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
		self._validate_private_conversion()
		self._validate_and_normalise_data()
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

	def _validate_and_normalise_data(self) -> None:
		"""Parse, validate, and reformat the ``data`` field.

		- Raises if the value is not valid JSON.
		- Raises if the parsed value is not a non-empty JSON object.
		- Reformats the stored JSON with consistent indentation.
		"""
		try:
			parsed_data = orjson.loads(self.data)
		except orjson.JSONDecodeError:
			frappe.throw(_("Template data must be valid JSON"))

		if not isinstance(parsed_data, dict) or not parsed_data:
			frappe.throw(_("Template data must be a non-empty JSON object"))

		self.data = frappe.as_json(parsed_data, indent=1)

	def _validate_private_conversion(self) -> None:
		old_doc = self.get_doc_before_save()
		if not old_doc:
			return

		if not self.private and old_doc.private and self.owner != frappe.session.user:
			frappe.throw(_("Only the owner can convert a private template to public"))


@frappe.whitelist()
def get_templates(
	reference_doctype: str,
	limit_start: int = 0,
	limit_page_length: int = 10,
	with_meta: bool = False,
) -> dict:
	"""Return templates for the manage dialog, filtered and sorted server-side.

	Sorting: ``disabled asc, private desc, template_name asc``

	Returns::

	    {"templates": [...], "has_next_page": bool, "total": int}
	"""
	user = frappe.session.user

	frappe.has_permission("Document Template", ptype="read", user=user, throw=True)

	if not frappe.has_permission(reference_doctype, ptype="create", user=user):
		frappe.throw(_("Not permitted to create {0}").format(reference_doctype), frappe.PermissionError)

	if with_meta:
		getdoctype("Document Template")

	all_templates = frappe.get_all(
		"Document Template",
		filters={"reference_doctype": reference_doctype},
		or_filters={"private": 0, "owner": user},
		fields="*",
		order_by="disabled asc, private desc, template_name asc",
	)

	start = max(0, int(limit_start))
	length = max(1, int(limit_page_length))
	end = start + length

	visible: list[dict] = []
	for template in all_templates:
		if not _has_user_permissions_on_template_data(template.pop("data"), template.reference_doctype, user):
			continue

		# only owner can see disabled templates
		if template.disabled and template.owner != user:
			continue

		visible.append(template)

		if len(visible) == end + 1:
			break

	return {
		"templates": visible[start:end],
		"has_next_page": end < len(visible),
	}


def _has_user_permissions_on_template_data(template_data: str, reference_doctype: str, user: str) -> bool:
	"""Build a temporary doc from template JSON and check full doc-level permissions.

	Uses ``frappe.permissions.has_permission`` with the constructed doc so that
	role permissions *and* user permissions (link-field restrictions) are both
	evaluated, matching the same path taken for real documents.
	"""
	data = orjson.loads(template_data)
	temp_doc = frappe.get_doc({"doctype": reference_doctype, "__islocal": 1, **data})
	return has_user_permission(temp_doc, user=user, strict=False)


def _is_system_manager(user: str) -> bool:
	return "System Manager" in frappe.get_roles(user)


def _get_creatable_doctypes(user: str) -> list[str]:
	"""Return list of doctypes *user* can create."""
	from frappe.utils.user import UserPermissions

	user_perms = UserPermissions(user)
	user_perms.build_permissions()
	return user_perms.can_create or []


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Row-level SQL filter for ``get_list`` / ``get_all``.

	- **System Manager** — sees all templates for DocTypes they can create.
	- **Template Manager** — public templates and own private templates,
	  scoped to doctypes they can create.
	- **Everyone else** — ``1=0`` (Can't access templates from Document Template list view).
	"""
	if not user:
		user = frappe.session.user

	has_write_perms_without_owner_restriction = get_role_permissions(
		"Document Template", user=user, is_owner=False
	).get("write")
	if not has_write_perms_without_owner_restriction:
		return "1=0"

	creatable = _get_creatable_doctypes(user)
	if not creatable:
		return "1=0"

	doctype_list = ", ".join(frappe.db.escape(dt) for dt in creatable)
	condition = f"`tabDocument Template`.`reference_doctype` IN ({doctype_list})"
	if not _is_system_manager(user):
		condition += f" AND (`tabDocument Template`.`private` = 0 OR `tabDocument Template`.`owner` = {frappe.db.escape(user)})"

	return condition


def has_permission(doc, user=None, ptype=None) -> bool:
	"""Doc-level permission check.

	Permission levels:

	1. **System Manager** — all operations allowed for doctypes they can create.
	2. **Owner** — all operations on own templates.
	3. **Template Manager** — read/write/delete public templates and
	   own private templates, scoped to doctypes they can create.
	4. **Desk Users** — create if they can create the reference doctype;
	   read/select public templates (subject to user permission checks);
	   no write/delete on others' templates.
	"""
	if not user:
		user = frappe.session.user

	if not frappe.has_permission(doc.reference_doctype, ptype="create", user=user):
		return False

	if ptype == "create":
		return True

	if not _has_user_permissions_on_template_data(doc.data, doc.reference_doctype, user):
		return False

	if doc.owner == user:
		return True

	if doc.private and not _is_system_manager(user):
		return False

	return True
