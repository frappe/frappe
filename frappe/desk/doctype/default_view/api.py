# The calls that set and clear one layer's default view of a doctype.

import frappe
from frappe import _
from frappe.desk.doctype.doctype_view.api import check_doctype, check_scope
from frappe.desk.doctype.doctype_view.doctype_view import PLAIN_VIEW, SITE_ROW
from frappe.desk.doctype.doctype_view.key_space import TYPE_KEYS

from .resolver import DefaultViews


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def save(doctype: str, key: str, scope: str) -> str | None:
	"""Point one layer's default at the view `key`, a type's name for its plain view; returns the caller's default."""
	check_doctype(doctype)
	check_scope(scope)
	if not isinstance(key, str) or not key:
		frappe.throw(_("A view key is one name."))

	layer = _layer(doctype, scope)
	_write(layer, _pointer(doctype, key, layer["user"]))

	return DefaultViews().addresses([doctype]).get(doctype)


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def clear(doctype: str, scope: str) -> str | None:
	"""Remove one layer's default; returns the caller's default from the layers left."""
	check_doctype(doctype)
	check_scope(scope)

	frappe.db.delete("Default View", _layer(doctype, scope))

	return DefaultViews().addresses([doctype]).get(doctype)


def _layer(doctype: str, scope: str) -> dict:
	# No `user` argument anywhere here: the user scope is the session user and nothing else.
	return {"reference_doctype": doctype, "user": frappe.session.user if scope == "user" else SITE_ROW}


def _pointer(doctype: str, key: str, user: str) -> dict:
	"""The row's view and type for `key`, refusing a saved view this layer cannot point at."""
	if view_type := TYPE_KEYS.get(key):
		return {"view": PLAIN_VIEW, "type": view_type}

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
