# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Who may change a Saved View or a Navigation Section.

Both DocTypes hold the same shape: a record with a `user` belongs to that user, and a
record without one is the shared area everybody sees. Who may write the shared area is
not a setting of its own -- it is whoever the Role Permission Manager grants write
*without* `if_owner`, since that is exactly the right to change a record you do not own.
Granting a role shared control is therefore a permission row, not code.
"""

import frappe
from frappe import _
from frappe.permissions import get_role_permissions
from frappe.utils import now


def can_manage_shared(doctype: str, user: str | None = None) -> bool:
	"""Whether the user's roles reach records they do not own, which the shared ones are."""
	perms = get_role_permissions(doctype, user=user or frappe.session.user, is_owner=False)
	return bool(perms.get("write"))


def own_personal_record(doc):
	"""A record created with a `user` is owned by that user, whoever wrote the row.

	`if_owner` asks about `owner` while these DocTypes scope on `user`; holding the two
	together is what lets the permission rows carry the whole rule. Otherwise a view an
	administrator seeded or migrated for someone is one its own user cannot edit.

	Only at insert: `owner` is `set_only_once`, so re-assigning it on a later save -- when a
	view moves across the shared boundary -- throws `CannotChangeConstantError`.
	"""
	if not doc.user or not doc.is_new():
		return

	doc.owner = doc.user

	# `set_user_and_timestamp` leaves `creation` unset under in_install/in_patch/in_migrate,
	# and `db_insert` reads that as its cue to stamp both `creation` and `owner` from the
	# session -- undoing the line above on exactly the seeded and migrated records it is for.
	if not doc.creation:
		doc.creation = now()


def guard_mutation(doc):
	"""Guard both sides of a move: the visibility a view is leaving and the one it is joining."""
	scopes = {doc.get("user") or ""}
	previous = doc.get_doc_before_save()
	if previous:
		scopes.add(previous.get("user") or "")

	guard_scopes(scopes, doc.doctype)


def guard_scopes(scopes: set[str], doctype: str):
	if can_manage_shared(doctype):
		return

	if "" in scopes:
		frappe.throw(_("Only a manager can change shared views."), frappe.PermissionError)

	if scopes - {frappe.session.user}:
		frappe.throw(_("You can only change your own views."), frappe.PermissionError)


def has_access(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Everyone reads the shared area; only a manager writes it."""
	user = user or frappe.session.user
	if can_manage_shared(doc.doctype, user):
		return True

	if doc.get("user"):
		return doc.get("user") == user

	return ptype in (None, "read", "select")


def query_conditions(doctype: str, user: str | None = None) -> str:
	"""A user reads the shared area plus their own records, and nobody else's."""
	user = user or frappe.session.user
	if can_manage_shared(doctype, user):
		return ""

	table = f"`tab{doctype}`"
	return f"(ifnull({table}.`user`, '') in ('', {frappe.db.escape(user)}))"
