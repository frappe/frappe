# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Who may change a Saved View or a Navigation Section."""

import frappe
from frappe import _

MANAGER_ROLES = ("System Manager",)


def can_manage_shared(user: str | None = None) -> bool:
	roles = set(frappe.get_roles(user or frappe.session.user))
	return bool(roles.intersection(manager_roles()))


def manager_roles() -> set[str]:
	return set(MANAGER_ROLES) | set(frappe.get_hooks("saved_view_manager_roles"))


def guard_mutation(doc):
	"""Guard both sides of a move: the visibility a view is leaving and the one it is joining."""
	scopes = {doc.get("user") or ""}
	previous = doc.get_doc_before_save()
	if previous:
		scopes.add(previous.get("user") or "")

	guard_scopes(scopes)


def guard_scopes(scopes: set[str]):
	if can_manage_shared():
		return

	if "" in scopes:
		frappe.throw(_("Only a manager can change shared views."), frappe.PermissionError)

	if scopes - {frappe.session.user}:
		frappe.throw(_("You can only change your own views."), frappe.PermissionError)


def has_access(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Everyone reads the shared area; only a manager writes it."""
	user = user or frappe.session.user
	if can_manage_shared(user):
		return True

	if doc.get("user"):
		return doc.get("user") == user

	return ptype in (None, "read", "select")


def query_conditions(doctype: str, user: str | None = None) -> str:
	"""A user reads the shared area plus their own records, and nobody else's."""
	user = user or frappe.session.user
	if can_manage_shared(user):
		return ""

	table = f"`tab{doctype}`"
	return f"(ifnull({table}.`user`, '') in ('', {frappe.db.escape(user)}))"
