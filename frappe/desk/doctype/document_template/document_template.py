# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class DocumentTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		data: DF.Code
		private: DF.Check
		reference_doctype: DF.Link
		template_name: DF.Data

	# end: auto-generated types

	def validate(self) -> None:
		self.template_name = self.template_name.strip()
		if not self.template_name:
			frappe.throw(frappe._("Template name is required."))
		if len(self.template_name) > 140:
			frappe.throw(frappe._("Template name must not exceed 140 characters."))

		try:
			json.loads(self.data)
		except (json.JSONDecodeError, TypeError, ValueError):
			frappe.throw(frappe._("Template data must be valid JSON."))

		self._validate_duplicate_name()

	def _validate_duplicate_name(self) -> None:
		"""Prevent duplicate template names within the same reference doctype.

		Two private templates owned by different users may share a name.
		All other combinations (public-public, public-private, same owner) are blocked.
		"""
		conflict = frappe.db.sql(
			"""
			SELECT name FROM `tabDocument Template`
			WHERE reference_doctype = %s
			  AND template_name = %s
			  AND name != %s
			  AND (private = 0 OR %s = 0 OR owner = %s)
			LIMIT 1
			""",
			(self.reference_doctype, self.template_name, self.name, self.private, self.owner),
		)
		if conflict:
			frappe.throw(
				frappe._("A template named {0} already exists for {1}.").format(
					frappe.bold(self.template_name),
					frappe.bold(self.reference_doctype),
				)
			)


def _is_system_manager(user: str) -> bool:
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Row-level filter for get_list / get_all queries.

	- System Manager / Administrator: see all templates.
	- Others: see public templates + their own private templates.
	"""
	if not user:
		user = frappe.session.user

	if _is_system_manager(user):
		return ""

	return f"(`tabDocument Template`.private = 0 OR `tabDocument Template`.owner = {frappe.db.escape(user)})"


def has_permission(doc: "DocumentTemplate", ptype: str, user: str | None = None) -> bool:
	"""Doc-level permission check.

	Rules:
	  1. System Manager / Administrator — all operations allowed.
	  2. Owner — all operations allowed on own templates.
	  3. Others (must be able to create the reference doctype):
	     - create: allowed
	     - read public templates: allowed
	     - write / delete any template: denied (owner + System Manager only)
	     - read private templates: denied (owner + System Manager only)
	"""
	if not user:
		user = frappe.session.user

	if _is_system_manager(user):
		return True

	if user == doc.owner:
		return True

	if not doc.reference_doctype:
		return False

	if not frappe.has_permission(doc.reference_doctype, "create", user=user):
		return False

	if ptype == "create":
		return True

	if not doc.private and ptype in ("read", "select"):
		return True

	return False


@frappe.whitelist()
def get_manageable_templates(reference_doctype: str) -> list[dict]:
	"""Return templates for the given doctype that the current user can edit/delete.

	System Manager / Administrator: all templates for the doctype.
	Others: only templates they own.
	"""
	user = frappe.session.user
	filters = {"reference_doctype": reference_doctype}

	if not _is_system_manager(user):
		filters["owner"] = user

	return frappe.get_list(
		"Document Template",
		fields=["name", "template_name", "owner", "private"],
		filters=filters,
		order_by="template_name asc",
	)


@frappe.whitelist()
def create_template(reference_doctype: str, template_name: str, private: int, data: str) -> str:
	"""Create a new Document Template and return its name."""
	doc = frappe.new_doc("Document Template")
	doc.reference_doctype = reference_doctype
	doc.template_name = template_name
	doc.private = frappe.utils.cint(private)
	doc.data = data
	doc.insert()
	return doc.name


@frappe.whitelist()
def update_template(name: str, data: str) -> None:
	"""Overwrite the captured data of an existing Document Template."""
	doc = frappe.get_doc("Document Template", name)
	doc.data = data
	doc.save()


@frappe.whitelist()
def get_template_data(name: str) -> str | None:
	"""Return the stored JSON data for a Document Template."""
	doc = frappe.get_doc("Document Template", name)
	if not has_permission(doc, "read"):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	return doc.data


@frappe.whitelist()
def delete_template(name: str) -> None:
	"""Whitelisted server-side delete with full permission enforcement."""
	frappe.delete_doc("Document Template", name)
