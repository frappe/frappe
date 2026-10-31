# Each view one person can open of some doctypes: the plain views, then their own, the site's and the apps'.

import frappe
from frappe import _
from frappe.desk.doctype.default_view.resolver import DefaultViews

from .app_views import app_view_doctypes, app_views
from .doctype_view import PLAIN_VIEW, SITE_ROW, VIEW_TYPES
from .key_space import TYPE_KEYS

# A doctype's own address opens its plain List view when no layer's default resolves.
FALLBACK_DEFAULT = VIEW_TYPES[0].lower()


class ViewList:
	"""One person's views in one app, each as `{key, label, type, layer, default}`; never their settings."""

	def __init__(self, user: str | None = None, app: str | None = None):
		self.user = user or frappe.session.user
		self.app = app

	def of(self, doctypes: list[str] | None = None) -> dict[str, list[dict]]:
		"""`{doctype: views}` for each of `doctypes` the person reads, else each they read that has a saved view."""
		rows = self.stored_rows(doctypes)
		if doctypes is None:
			doctypes = {row.reference_doctype for row in rows} | set(app_view_doctypes())
		names = self.readable(doctypes)
		defaults = DefaultViews(self.user, self.app).addresses(names)

		return {doctype: self.views(doctype, rows, defaults.get(doctype)) for doctype in names}

	def stored_rows(self, doctypes: list[str] | None) -> list[frappe._dict]:
		"""The person's own saved views and the site's, by label, in one query on `Doctype View`."""
		filters = {"key": ("!=", PLAIN_VIEW), "user": ("in", (self.user, SITE_ROW))}
		if doctypes is not None:
			filters["reference_doctype"] = ("in", doctypes)

		rows = frappe.get_all(
			"Doctype View", filters=filters, fields=["reference_doctype", "key", "label", "type", "user"]
		)
		return sorted(rows, key=lambda row: (row.label.casefold(), row.key))

	def readable(self, doctypes) -> list[str]:
		"""The doctypes still on the site that the person reads, by name."""
		if not doctypes:
			return []

		existing = frappe.get_all("DocType", filters={"name": ("in", list(doctypes))}, pluck="name")
		return sorted(
			doctype for doctype in existing if frappe.has_permission(doctype, "read", user=self.user)
		)

	def views(self, doctype: str, rows: list[frappe._dict], default: str | None) -> list[dict]:
		"""The doctype's views in lookup order, each key once at its first layer, the default marked."""
		listed = {}
		for view in (*plain_views(), *self.saved_views(doctype, rows)):
			listed.setdefault(view["key"], view)

		default = default or FALLBACK_DEFAULT
		return [{**view, "default": key == default} for key, view in listed.items()]

	def saved_views(self, doctype: str, rows: list[frappe._dict]) -> list[dict]:
		"""The person's own, then the site's, then the apps', each layer by label."""
		stored = [
			listed_view(row.key, row.label, row.type, layer)
			for layer, user in (("own", self.user), ("site", SITE_ROW))
			for row in rows
			if row.reference_doctype == doctype and row.user == user
		]
		shipped = [
			listed_view(key, _(view.label), view.type, "app") for key, view in app_views(doctype).items()
		]
		return [*stored, *sorted(shipped, key=lambda view: (view["label"].casefold(), view["key"]))]


def plain_views() -> list[dict]:
	"""Each view type's plain view, at `/<doctype>/view/<type>`; it belongs to no layer."""
	return [listed_view(key, _(type), type, None) for key, type in TYPE_KEYS.items()]


def listed_view(key: str, label: str, type: str, layer: str | None) -> dict:
	return {"key": key, "label": label, "type": type, "layer": layer}
