# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from collections import Counter
from json import loads

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.permissions import AUTOMATIC_ROLES


class WorkspaceVariant(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		content: DF.LongText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		role: DF.Link
		widgets: DF.LongText | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Workspace Variant"


def sanitize_variants(rows) -> None:
	"""The same trip through the XSS sanitizer the fields they mirror take."""
	from frappe.desk.doctype.workspace.workspace import sanitize_content

	for row in rows:
		row.content = sanitize_content(row.content)
		row.widgets = sanitize_content(row.widgets)


def validate_variants(rows) -> None:
	"""A layout is bound to one role a person can lack, and its widget labels are unique."""
	seen = set()
	for row in rows:
		if row.role in AUTOMATIC_ROLES:
			frappe.throw(
				_("A layout cannot be bound to {0}, which every user holds.").format(_(row.role)),
				title=_("Role Layouts"),
			)
		if row.role in seen:
			frappe.throw(_("{0} has more than one layout.").format(_(row.role)), title=_("Role Layouts"))
		seen.add(row.role)

		try:
			widgets = loads(row.widgets or "{}")
		except ValueError:
			frappe.throw(_("The {0} layout's widgets are not valid JSON.").format(_(row.role)))

		for widget_type, items in widgets.items():
			counts = Counter(item.get("label") for item in items)
			duplicates = sorted(label for label, count in counts.items() if label and count > 1)
			if duplicates:
				frappe.throw(
					_("The {0} layout has two {1} widgets labelled {2}.").format(
						_(row.role), widget_type, frappe.bold(", ".join(duplicates))
					),
					title=_("Duplicate Label"),
				)
