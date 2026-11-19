# The calls that set and clear one layer's default view of a doctype.

import frappe
from frappe import _
from frappe.desk.doctype.doctype_view.api import check_doctype, check_scope
from frappe.desk.doctype.doctype_view.app_views import app_views
from frappe.desk.doctype.doctype_view.doctype_view import PLAIN_VIEW, SITE_ROW
from frappe.desk.doctype.view_type.view_type import refuse_where_it_does_not_apply, type_keys

from .resolver import DefaultViews


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def save(doctype: str, key: str, scope: str, app: str | None = None) -> str | None:
	"""Point one layer's default at the view `key`, a type's name for its plain view; returns the caller's default in `app`."""
	check_doctype(doctype)
	check_scope(scope)
	if not isinstance(key, str) or not key:
		frappe.throw(_("A view key is one name."))

	layer = _layer(doctype, scope)
	_write(layer, _pointer(doctype, key, layer["user"]))

	return _resolved(doctype, app)


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def clear(doctype: str, scope: str, app: str | None = None) -> str | None:
	"""Remove one layer's default; returns the caller's default in `app` from the layers left."""
	check_doctype(doctype)
	check_scope(scope)

	frappe.db.delete("Default View", _layer(doctype, scope))

	return _resolved(doctype, app)


def _resolved(doctype: str, app: str | None) -> str | None:
	return DefaultViews(app=app).addresses([doctype]).get(doctype)


def _layer(doctype: str, scope: str) -> dict:
	# No `user` argument anywhere here: the user scope is the session user and nothing else.
	return {"reference_doctype": doctype, "user": frappe.session.user if scope == "user" else SITE_ROW}


def _pointer(doctype: str, key: str, user: str) -> dict:
	"""The row's view and type for `key`, refusing a saved view this layer cannot point at."""
	if view_type := type_keys().get(key):
		refuse_where_it_does_not_apply(view_type, doctype)
		return {"view": PLAIN_VIEW, "type": view_type}

	if key in app_views(doctype):
		return {"view": key, "type": None}

	# The site's default may name only a site view: anyone else would pass over a person's own.
	if not frappe.db.exists(
		"Doctype View", {"reference_doctype": doctype, "key": key, "user": ("in", {user, SITE_ROW})}
	):
		raise frappe.DoesNotExistError(_("This view doesn't exist."))

	return {"view": key, "type": None}


def _write(layer: dict, pointer: dict):
	# `ignore_permissions`: the gate is `check_scope`'s; a Desk User has no write on the doctype.
	name = frappe.db.get_value("Default View", layer)
	doc = (
		frappe.get_doc("Default View", name) if name else frappe.get_doc({"doctype": "Default View", **layer})
	)
	doc.update(pointer)
	doc.save(ignore_permissions=True)
