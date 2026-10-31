# What a doctype's own address opens for one person: the first default, own then site then app, that resolves.

import frappe
from frappe.desk.doctype.doctype_view.app_views import app_defaults
from frappe.desk.doctype.doctype_view.doctype_view import SITE_ROW, VIEW_TYPES
from frappe.desk.doctype.doctype_view.key_space import find_views


class DefaultViews:
	"""One person's default views in one app, each named by its address's last segment: `/<doctype>/view/<segment>`."""

	def __init__(self, user: str | None = None, app: str | None = None):
		self.user = user or frappe.session.user
		self.app = app

	def addresses(self, doctypes: list[str] | None = None) -> dict[str, str]:
		"""`{doctype: segment}` for each doctype the person reads whose default resolves at some layer."""
		layers = [*self.stored_layers(doctypes), self.app_layer(doctypes)]
		keyed = [
			(doctype, pointer.view) for layer in layers for doctype, pointer in layer.items() if pointer.view
		]
		views = find_views(keyed, self.user)

		resolved = {}
		for doctype in self.existing({doctype for layer in layers for doctype in layer}):
			segments = (segment(doctype, layer.get(doctype), views) for layer in layers)
			first = next((found for found in segments if found), None)
			if first and frappe.has_permission(doctype, "read", user=self.user):
				resolved[doctype] = first
		return resolved

	def stored_layers(self, doctypes: list[str] | None) -> list[dict[str, frappe._dict]]:
		"""The person's pointers, then the site's, in one query on `Default View`."""
		filters = {"user": ("in", (self.user, SITE_ROW))}
		if doctypes is not None:
			filters["reference_doctype"] = ("in", doctypes)

		rows = frappe.get_all(
			"Default View", filters=filters, fields=["reference_doctype", "user", "view", "type"]
		)
		return [
			{row.reference_doctype: row for row in rows if row.user == layer_user}
			for layer_user in (self.user, SITE_ROW)
		]

	def app_layer(self, doctypes: list[str] | None) -> dict[str, frappe._dict]:
		"""The defaults apps' view files declare: this app's, else the one the doctype's own app ships."""
		return {
			view.doctype: frappe._dict(view=view.key, type=None)
			for view in app_defaults(self.app)
			if doctypes is None or view.doctype in doctypes
		}

	def existing(self, doctypes: set[str]) -> list[str]:
		"""The doctypes still on the site: deleting a DocType leaves the rows that point at it."""
		if not doctypes:
			return []

		return frappe.get_all("DocType", filters={"name": ("in", doctypes)}, pluck="name")


def segment(doctype: str, pointer: frappe._dict | None, views: dict) -> str | None:
	"""The pointer's address segment while it resolves for the person: a view they see, or a known type."""
	if pointer is None:
		return None

	if pointer.view:
		return pointer.view if (doctype, pointer.view) in views else None

	return pointer.type.lower() if pointer.type in VIEW_TYPES else None
