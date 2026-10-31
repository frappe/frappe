# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.doctype_view.doctype_view import PLAIN_VIEW, SITE_ROW, VIEW_TYPES
from frappe.model.document import Document


class DuplicateDefaultError(frappe.ValidationError):
	pass


class DefaultView(Document):
	"""One layer's pointer to the view a doctype's own address opens: a saved view's key, or a type's plain view."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		reference_doctype: DF.Link
		type: DF.Data | None
		user: DF.Link
		view: DF.Data
	# end: auto-generated types

	def validate(self):
		self.user = self.user or SITE_ROW
		self.view = self.view or PLAIN_VIEW
		if self.view:
			self.type = None
		elif self.type not in VIEW_TYPES:
			frappe.throw(
				_("{0} is not a view type.").format(frappe.bold(self.type)), title=_("Unknown View Type")
			)
		self.refuse_a_second_default()

	def refuse_a_second_default(self):
		"""Refuse the duplicate here: `db_insert` would read the unique index's refusal as a hash retry."""
		existing = frappe.db.get_value(
			self.doctype, {"reference_doctype": self.reference_doctype, "user": self.user}
		)

		if existing and existing != self.name:
			frappe.throw(
				_("{0} already has a default view at this layer. Edit {1} instead.").format(
					frappe.bold(self.reference_doctype), frappe.bold(existing)
				),
				title=_("Already Exists"),
				exc=DuplicateDefaultError,
			)


def on_doctype_update():
	"""One default per doctype per layer; `user` first, so boot's read of one person's rows uses it."""
	frappe.db.add_unique(
		"Default View",
		("user", "reference_doctype"),
		constraint_name="unique_default_view",
	)
