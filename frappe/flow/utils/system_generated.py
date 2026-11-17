# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Guards for rows flagged `is_system_generated`.

Such rows are owned by the app that ships them: permission-checked (Desk/API)
writes cannot break them, while the owning app keeps full control by passing
`ignore_permissions=True`. Renames are blocked outright because frappe's
rename_doc never propagates ignore_permissions to the doc.
"""

from __future__ import annotations

from contextlib import contextmanager

import click

import frappe
from frappe import _


def validate_immutable(doc, fields: tuple[str, ...] = ()) -> None:
	"""Call from validate. Blocks unsetting the flag and edits to `fields` (columns, or Table
	MultiSelect fields compared by their rows' links), against DB values so tampering with the
	flag can't disarm the other guards."""
	if doc.is_new() or doc.flags.ignore_permissions:
		return
	tables = [f for f in fields if doc.meta.get_field(f).fieldtype == "Table MultiSelect"]
	columns = [f for f in fields if f not in tables]
	before = frappe.db.get_value(doc.doctype, doc.name, ["is_system_generated", *columns], as_dict=True)
	if not before or not before.is_system_generated:
		return
	if not doc.is_system_generated:
		frappe.throw(
			_("Cannot remove the system-generated flag from {0} {1}.").format(_(doc.doctype), doc.name),
			title=_("Protected"),
		)
	for fieldname in fields:
		if fieldname in tables:
			saved, current = _table_links(doc, fieldname)
		else:
			saved, current = before.get(fieldname), doc.get(fieldname)
		if saved != current:
			frappe.throw(
				_("Cannot change {0} of system-generated {1} {2}.").format(
					_(doc.meta.get_label(fieldname)), _(doc.doctype), doc.name
				),
				title=_("Protected"),
			)


def _table_links(doc, fieldname: str) -> tuple[list, list]:
	"""The saved and the current link values of a Table MultiSelect field, in row order."""
	df = doc.meta.get_field(fieldname)
	link = next(f.fieldname for f in frappe.get_meta(df.options).fields if f.fieldtype == "Link")
	saved = frappe.get_all(
		df.options, {"parent": doc.name, "parentfield": fieldname}, pluck=link, order_by="idx"
	)
	return saved, [row.get(link) for row in doc.get(fieldname)]


def block_delete(doc, always: bool = False) -> None:
	"""Call from on_trash. The owning app deletes with ignore_permissions, e.g. in a patch
	after a rename; `always=True` blocks even that, for Flow's own builtin agent and tools."""
	if doc.is_system_generated and (always or not doc.flags.ignore_permissions):
		frappe.throw(
			_("Cannot delete system-generated {0} {1}.").format(_(doc.doctype), doc.name),
			title=_("Protected"),
		)


def block_rename(doc, old: str) -> None:
	"""Call from before_rename."""
	if doc.is_system_generated:
		frappe.throw(
			_("Cannot rename system-generated {0} {1}.").format(_(doc.doctype), old),
			title=_("Protected"),
		)


def block_insert(doc) -> None:
	"""Call from before_insert, for doctypes whose `app` names the row: only the owning app creates
	system-generated rows, passing ignore_permissions."""
	if (doc.is_system_generated or doc.app) and not doc.flags.ignore_permissions:
		frappe.throw(
			_("Only an app can create a system-generated {0}.").format(_(doc.doctype)),
			title=_("Protected"),
		)


def block_slash_in_name(doc, name: str | None = None) -> None:
	"""Call from validate, and from before_rename with the new name: the site's own rows cannot
	take a `/`, which marks the rows apps ship."""
	if not doc.app and "/" in (name or doc.name):
		frappe.throw(_("{0} names cannot contain /.").format(_(doc.doctype)), title=_("Invalid Name"))


def log_skipped(title: str, reason: str) -> None:
	"""Report an app's row that a sync leaves out, so migrate goes on without it."""
	click.secho(f"{title}: {frappe.utils.strip_html_tags(reason)}", fg="yellow")
	frappe.log_error(title=title, message=reason)


@contextmanager
def skip_if_invalid(title: str):
	"""Sync one of an app's rows; if the app defines it wrongly, undo it and log it under `title`."""
	savepoint = f"flow_{frappe.generate_hash(length=10)}"
	frappe.db.savepoint(savepoint)
	try:
		yield
	except frappe.ValidationError as e:
		frappe.db.rollback(save_point=savepoint)
		log_skipped(title, str(e))
	else:
		frappe.db.release_savepoint(savepoint)
