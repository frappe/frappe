# One person's writes to the saved views of a doctype: each is held to the rules of the layer its view sits in.

import frappe
from frappe import _
from frappe.desk.doctype.view_type.view_type import type_keys

from .app_views import app_view_settings, app_views
from .doctype_view import SITE_ROW, is_site_administrator
from .key_space import KeySpace


def layer_of(view: frappe._dict) -> str:
	"""`own`, `site` or `app`: where the view's row sits; an app's view has no row and no user."""
	if view.user is None:
		return "app"
	return "site" if view.user == SITE_ROW else "own"


def can_save(layer: str | None) -> bool:
	"""A person saves their own views and a plain view; the site's and the apps' take a site administrator."""
	return layer in (None, "own") or is_site_administrator()


def settings_of(view: frappe._dict) -> dict | None:
	"""The settings of a saved view: its row's, or its file's for an app's."""
	if layer_of(view) == "app":
		return app_view_settings(view.reference_doctype, view.key)

	parsed = frappe.parse_json(frappe.db.get_value("Doctype View", view.name, "settings") or "null")
	return parsed if isinstance(parsed, dict) else None


class ViewWriter:
	"""Saves, renames, deletes and publishes the saved views of one doctype for the session user."""

	def __init__(self, doctype: str):
		self.doctype = doctype

	def save(self, key: str, settings: dict) -> frappe._dict:
		"""Replace the view's settings; a site administrator's save of an app view writes a site row over it."""
		view = self.saved(key)
		self.refuse_unless_site_administrator(view)

		if layer_of(view) == "app":
			return self.override(view, settings)

		doc = frappe.get_doc("Doctype View", view.name)
		doc.settings = settings
		# `ignore_permissions`: the gate is the layer's, above; a Desk User has no write on the doctype.
		doc.save(ignore_permissions=True)
		return view

	def save_as(self, label: str, settings: dict, type: str) -> frappe._dict:
		"""A new view in the person's own layer; `Doctype View` makes its key from the label."""
		doc = frappe.get_doc(
			{
				"doctype": "Doctype View",
				"reference_doctype": self.doctype,
				"type": type,
				"user": frappe.session.user,
				"label": self.labelled(label),
				"settings": settings,
			}
		).insert(ignore_permissions=True)
		return self.saved(doc.key)

	def rename(self, key: str, label: str) -> frappe._dict:
		"""Change the label only; the key is the address and stays."""
		view = self.row_of(key, _("An app's view is renamed in its file."))
		doc = frappe.get_doc("Doctype View", view.name)
		doc.label = self.labelled(label)
		doc.save(ignore_permissions=True)
		return self.saved(key)

	def delete(self, key: str) -> bool:
		"""Delete the row; whether an app's view answers at the key again is the reply."""
		view = self.row_of(key, _("An app's view is deleted by removing its file."))
		frappe.delete_doc("Doctype View", view.name, ignore_permissions=True, delete_permanently=True)
		return key in app_views(self.doctype)

	def publish(self, key: str) -> frappe._dict:
		"""Move the person's own view to the site layer under the same key, so its stars and defaults still resolve."""
		if not is_site_administrator():
			self.refuse_site_rows()
		view = self.saved(key)
		if layer_of(view) != "own":
			frappe.throw(_("Only your own views can be published."), title=_("Not Your View"))
		if key in app_views(self.doctype):
			frappe.throw(
				_("{0} is the address of an app's view, so this view cannot move to the site.").format(
					frappe.bold(key)
				),
				title=_("Address Taken"),
			)

		doc = frappe.get_doc("Doctype View", view.name)
		doc.user = SITE_ROW
		doc.save(ignore_permissions=True)
		return self.saved(key)

	def saved(self, key: str) -> frappe._dict:
		"""The saved view at `key` the person sees, with its layer; a type's plain view is not one."""
		view = None if key in type_keys() else KeySpace(self.doctype).find(key)
		if not view:
			raise frappe.DoesNotExistError(_("This view doesn't exist."))

		view.layer = layer_of(view)
		view.reference_doctype = self.doctype
		return view

	def row_of(self, key: str, app_message: str) -> frappe._dict:
		"""The view at `key`, once it is one the person may change as a row: not an app's, and a site row only for an administrator."""
		view = self.saved(key)
		if view.layer == "app":
			frappe.throw(app_message, title=_("App View"))
		self.refuse_unless_site_administrator(view)
		return view

	def refuse_unless_site_administrator(self, view: frappe._dict):
		if view.layer != "own" and not is_site_administrator():
			self.refuse_site_rows()

	def override(self, view: frappe._dict, settings: dict) -> frappe._dict:
		"""A site row at the app view's key: it replaces the app's view for everyone, under its label and type."""
		# The file's own label: the row's label is the saver's translation of it.
		label = app_views(self.doctype)[view.key].label
		frappe.get_doc(
			{
				"doctype": "Doctype View",
				"reference_doctype": self.doctype,
				"type": view.type,
				"user": SITE_ROW,
				"key": view.key,
				"label": label,
				"settings": settings,
			}
		).insert(ignore_permissions=True)
		return self.saved(view.key)

	def labelled(self, label: str) -> str:
		label = label.strip()
		if not label:
			frappe.throw(_("A view needs a name."), title=_("Name Missing"))
		return label

	def refuse_site_rows(self):
		frappe.throw(
			_("Only a System Manager may change what everyone on this site sees."),
			frappe.PermissionError,
		)
