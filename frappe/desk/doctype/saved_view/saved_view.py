# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.desk.doctype.saved_view.permissions import (
	guard_mutation,
	guard_scopes,
	has_access,
	query_conditions,
)
from frappe.model.document import Document


class SavedView(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		column_field: DF.Data | None
		columns: DF.Code | None
		filters: DF.Code | None
		group_by_field: DF.Data | None
		icon: DF.Data | None
		is_default: DF.Check
		kanban_columns: DF.Code | None
		kanban_fields: DF.Code | None
		label: DF.Data
		order_by: DF.Code | None
		reference_doctype: DF.Link
		rows: DF.Code | None
		title_field: DF.Data | None
		type: DF.Literal["list", "group_by", "kanban"]
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		guard_mutation(self)
		self.validate_default_is_personal()

	def validate_default_is_personal(self):
		"""A shared view is never the auto-saved default; that record is always per-user."""
		if self.is_default and not self.user:
			frappe.throw(_("A default Saved View must belong to a user."), frappe.ValidationError)

	def on_trash(self):
		guard_scopes({self.user or ""})


def get_permission_query_conditions(user: str | None = None) -> str:
	return query_conditions("Saved View", user)


def has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	return has_access(doc, ptype, user)
