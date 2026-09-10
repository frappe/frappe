# The three calls a view's settings go through: read both scopes, patch keys, clear one key.

import frappe
from frappe import _

from .doctype_view import PLAIN_VIEW, SITE_ROW, VIEW_TYPES, DuplicateViewError, is_site_administrator

SCOPES = ("user", "site")


@frappe.whitelist()
def get(doctype: str, type: str = "List") -> dict:
	"""The site row's and the caller's own `settings` for this view, either `None` when absent."""
	_check(doctype, type)

	return _rows(doctype, type)


@frappe.whitelist()
def save(doctype: str, type: str, scope: str, settings: dict) -> dict:
	"""Patch the keys given onto one scope's row, creating it, and hand back both scopes."""
	_check(doctype, type, scope)
	if not isinstance(settings, dict):
		frappe.throw(_("The settings of a view are one object."), title=_("Not Settings"))

	_apply(_address(doctype, type, scope), lambda stored: {**stored, **settings})

	return _rows(doctype, type)


@frappe.whitelist()
def reset(doctype: str, type: str, scope: str, key: str) -> dict:
	"""Clear one key on one scope's row, deleting the row when nothing is left."""
	_check(doctype, type, scope)
	if not isinstance(key, str):
		frappe.throw(_("A settings key is one name."))

	_apply(_address(doctype, type, scope), lambda stored: {k: v for k, v in stored.items() if k != key})

	return _rows(doctype, type)


def _check(doctype: str, type: str, scope: str = "user"):
	"""Refuse an argument the caller cannot use, and the site scope for anyone but a System Manager."""
	# Explicit: `validate_argument_types` only runs in a request, and `doctype` goes into a filter.
	if not all(isinstance(argument, str) for argument in (doctype, type, scope)):
		frappe.throw(_("A doctype, a view type and a scope are each one name."))

	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("{0} is not a doctype.").format(frappe.bold(doctype)))

	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You are not permitted to read {0}.").format(doctype), frappe.PermissionError)

	if type not in VIEW_TYPES:
		frappe.throw(_("{0} is not a view type.").format(frappe.bold(type)))

	if scope not in SCOPES:
		frappe.throw(_("{0} is not a settings scope.").format(scope))

	if scope == "site" and not is_site_administrator():
		frappe.throw(
			_("Only a System Manager may change what everyone on this site sees."),
			frappe.PermissionError,
		)


def _address(doctype: str, type: str, scope: str) -> dict:
	# No `user` argument anywhere here: the user scope is the session user and nothing else.
	return {
		"reference_doctype": doctype,
		"type": type,
		"user": frappe.session.user if scope == "user" else SITE_ROW,
		"label": PLAIN_VIEW,
	}


def _rows(doctype: str, type: str) -> dict:
	rows = frappe.get_all(
		"Doctype View",
		filters={
			"reference_doctype": doctype,
			"type": type,
			"label": PLAIN_VIEW,
			"user": ("in", (SITE_ROW, frappe.session.user)),
		},
		fields=["user", "settings"],
	)
	by_user = {row.user: _parsed(row.settings) for row in rows}

	return {"site": by_user.get(SITE_ROW), "user": by_user.get(frappe.session.user)}


def _apply(address: dict, change):
	"""Read, change and write under the row lock; a first write that loses the race to a twin runs again on the twin's row."""
	frappe.db.savepoint("doctype_view_write")
	try:
		_write(address, change)
	except (frappe.UniqueValidationError, DuplicateViewError):
		frappe.db.rollback(save_point="doctype_view_write")
		_write(address, change)


def _locked(address: dict) -> tuple[str | None, dict]:
	"""The row at this address, locked until the write lands so two tabs cannot drop each other's key."""
	row = frappe.db.get_value("Doctype View", address, ["name", "settings"], as_dict=True, for_update=True)

	return (row.name, _parsed(row.settings) or {}) if row else (None, {})


def _parsed(settings) -> dict | None:
	parsed = frappe.parse_json(settings) if settings else None

	return parsed if isinstance(parsed, dict) else None


def _write(address: dict, change):
	"""Put the changed settings at this address, and delete the row when there are none."""
	# `ignore_permissions`: the gate is `_check`'s; a Desk User has no write on the doctype.
	existing, stored = _locked(address)
	settings = change(stored)

	if not settings:
		if existing:
			frappe.delete_doc("Doctype View", existing, ignore_permissions=True, delete_permanently=True)
		return

	doc = (
		frappe.get_doc("Doctype View", existing)
		if existing
		else frappe.get_doc({"doctype": "Doctype View", **address})
	)
	doc.settings = settings
	doc.save(ignore_permissions=True)
