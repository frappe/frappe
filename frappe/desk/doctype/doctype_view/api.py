# The calls a view's settings go through: read both scopes, patch keys, clear one key; find a saved view by key, list them,
# read one's settings, and save, rename, delete and publish them.

import frappe
from frappe import _
from frappe.desk.doctype.default_view.resolver import DefaultViews
from frappe.desk.doctype.favourite.favourite import list_favourites
from frappe.desk.doctype.view_type.view_type import (
	applies_to,
	refuse_where_it_does_not_apply,
	type_keys,
	view_types,
)

from .app_views import app_plain_settings
from .doctype_view import PLAIN_VIEW, SITE_ROW, DuplicateViewError, is_site_administrator
from .key_space import KeySpace
from .saved_view import ViewWriter, can_save, layer_of, settings_of
from .view_list import ViewList

SCOPES = ("user", "site")


@frappe.desk_v2_only
@frappe.whitelist()
def get(doctype: str, type: str = "List") -> dict:
	"""The app's `settings` and both scopes', each `None` when absent, and which of the list and its saved views the caller starred."""
	_check(doctype, type)

	return {**_rows(doctype, type), "favourites": list_favourites(doctype)}


@frappe.desk_v2_only
@frappe.whitelist()
def save(doctype: str, type: str, scope: str, settings: dict) -> dict:
	"""Patch the keys given onto one scope's row, creating it, and hand back both scopes."""
	_check(doctype, type, scope)
	if not isinstance(settings, dict):
		frappe.throw(_("The settings of a view are one object."), title=_("Not Settings"))

	_apply(_address(doctype, type, scope), lambda stored: {**stored, **settings})

	return _rows(doctype, type)


@frappe.desk_v2_only
@frappe.whitelist()
def reset(doctype: str, type: str, scope: str, key: str) -> dict:
	"""Clear one key on one scope's row, deleting the row when nothing is left."""
	_check(doctype, type, scope)
	if not isinstance(key, str):
		frappe.throw(_("A settings key is one name."))

	_apply(_address(doctype, type, scope), lambda stored: {k: v for k, v in stored.items() if k != key})

	return _rows(doctype, type)


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def find(doctype: str, key: str) -> dict:
	"""The view at `key` the caller sees: a view type's plain view, else their own before the site's before an app's; another person's reads as missing."""
	if not isinstance(key, str):
		frappe.throw(_("A view key is one name."))
	check_doctype(doctype)

	if type := type_keys().get(key):
		return _found(doctype, key, _(view_types()[type].label), type, None)

	view = KeySpace(doctype).find(key)
	if not view:
		raise frappe.DoesNotExistError(_("This view doesn't exist."))

	return _found(doctype, view.key, view.label, view.type, layer_of(view))


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def list_views(doctype: str | None = None, app: str | None = None) -> dict[str, list[dict]]:
	"""`{doctype: views}` the caller can open, of `doctype` or else of every doctype they read that has a saved view."""
	if doctype is None:
		return ViewList(app=app).of()

	check_doctype(doctype)
	return ViewList(app=app).of([doctype])


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def view_settings(doctype: str, key: str) -> dict:
	"""The settings of the view at `key`, from the layer the caller sees it at (a type's plain view: its layers merged), and whether they may save it."""
	if not isinstance(key, str):
		frappe.throw(_("A view key is one name."))
	check_doctype(doctype)

	if type := type_keys().get(key):
		rows = _rows(doctype, type)
		settings = {**(rows["app"] or {}), **(rows["site"] or {}), **(rows["user"] or {})}
		return {
			**_found(doctype, key, _(view_types()[type].label), type, None),
			"settings": settings,
			"saveable": True,
		}

	view = KeySpace(doctype).find(key)
	if not view:
		raise frappe.DoesNotExistError(_("This view doesn't exist."))

	layer = layer_of(view)
	view.reference_doctype = doctype
	return {
		**_found(doctype, view.key, view.label, view.type, layer),
		"settings": settings_of(view) or {},
		"saveable": can_save(layer),
	}


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def save_view(doctype: str, key: str, settings: dict) -> dict:
	"""Replace a saved view's settings. A site administrator's save of an app's view writes a site row at its key."""
	check_doctype(doctype)

	return _written(doctype, ViewWriter(doctype).save(key, settings))


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def save_view_as(doctype: str, label: str, settings: dict, type: str = "List") -> dict:
	"""Make a new view of `type` in the caller's own layer; its key comes from the label, and the reply is the view."""
	check_doctype(doctype)
	refuse_where_it_does_not_apply(type, doctype)

	return _written(doctype, ViewWriter(doctype).save_as(label, settings, type))


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def rename_view(doctype: str, key: str, label: str) -> dict:
	"""Change a saved view's label. Its key, and so its address, stays."""
	check_doctype(doctype)

	return _written(doctype, ViewWriter(doctype).rename(key, label))


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def delete_view(doctype: str, key: str, app: str | None = None) -> dict:
	"""Delete a saved view's row. `restored` is true when that brought back an app's view at the same key;
	`default_view` is the caller's default in `app` once it is gone, from the layers left."""
	check_doctype(doctype)

	restored = ViewWriter(doctype).delete(key)
	return {
		"key": key,
		"restored": restored,
		"default_view": DefaultViews(app=app).addresses([doctype]).get(doctype),
	}


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def publish_view(doctype: str, key: str) -> dict:
	"""Move the caller's own view to the site layer under the same key; a System Manager's act."""
	check_doctype(doctype)

	return _written(doctype, ViewWriter(doctype).publish(key))


def _written(doctype: str, view: frappe._dict) -> dict:
	return _found(doctype, view.key, view.label, view.type, view.layer)


def _found(doctype: str, key: str, label: str, type: str, layer: str | None) -> dict:
	"""A view as the page opens it; `applies` is false when its type no longer fits the doctype."""
	return {"key": key, "label": label, "type": type, "layer": layer, "applies": applies_to(type, doctype)}


def _check(doctype: str, type: str, scope: str = "user"):
	"""Refuse an argument the caller cannot use, and the site scope for anyone but a System Manager."""
	check_doctype(doctype)
	if not all(isinstance(argument, str) for argument in (type, scope)):
		frappe.throw(_("A doctype, a view type and a scope are each one name."))

	if type not in view_types():
		frappe.throw(_("{0} is not a view type.").format(frappe.bold(type)))
	refuse_where_it_does_not_apply(type, doctype)

	check_scope(scope)


def check_scope(scope: str):
	"""Refuse a scope that is not one, and the site scope for anyone but a System Manager."""
	if scope not in SCOPES:
		frappe.throw(_("{0} is not a settings scope.").format(scope))

	if scope == "site" and not is_site_administrator():
		frappe.throw(
			_("Only a System Manager may change what everyone on this site sees."),
			frappe.PermissionError,
		)


def check_doctype(doctype: str):
	"""Refuse a doctype that is not one, or that the caller cannot read."""
	# Explicit: `validate_argument_types` only runs in a request, and `doctype` goes into a filter.
	if not isinstance(doctype, str):
		frappe.throw(_("A doctype is one name."))

	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("{0} is not a doctype.").format(frappe.bold(doctype)))

	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You are not permitted to read {0}.").format(doctype), frappe.PermissionError)


def _address(doctype: str, type: str, scope: str) -> dict:
	# No `user` argument anywhere here: the user scope is the session user and nothing else.
	return {
		"reference_doctype": doctype,
		"type": type,
		"user": frappe.session.user if scope == "user" else SITE_ROW,
		"key": PLAIN_VIEW,
	}


def _rows(doctype: str, type: str) -> dict:
	rows = frappe.get_all(
		"Doctype View",
		filters={
			"reference_doctype": doctype,
			"type": type,
			"key": PLAIN_VIEW,
			"user": ("in", (SITE_ROW, frappe.session.user)),
		},
		fields=["user", "settings"],
	)
	by_user = {row.user: _parsed(row.settings) for row in rows}

	return {
		"app": app_plain_settings(doctype, type),
		"site": by_user.get(SITE_ROW),
		"user": by_user.get(frappe.session.user),
	}


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
