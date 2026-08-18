# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.app_state import is_module_disabled
from frappe.model.document import Document

PAGE_SCRIPT_VIEWS = ("Record",)
PAGE_SCRIPT_CHANGED = "page_script_changed"
# `run_order` is a pure sort key, not a unique one: ties are legal -- a fixture from a
# third-party app, a reorder that lost a race -- and `creation` breaks them, which is the
# rule the tier ran on before anyone could reorder anything.
PAGE_SCRIPT_ORDER = "run_order asc, creation asc"


class PageScript(Document):
	def on_update(self):
		self.notify_change()

	def on_trash(self):
		self.notify_change()

	# Broadcast, not per-user: every mounted page of this doctype replays the tier,
	# and the payload names the doctype only — never the script text.
	def notify_change(self):
		frappe.publish_realtime(
			PAGE_SCRIPT_CHANGED, {"dt": self.dt, "view": self.view}, after_commit=True
		)


@frappe.whitelist()
def get_page_scripts(dt: str, view: str = "Record"):
	"""Return the scripts a Record page of `dt` runs, in run order."""
	_validate_target(dt, view)
	# Reading the doctype is the gate: whoever may open the record receives its
	# scripts, exactly as desk ships `__custom_js` inside meta.
	frappe.has_permission(dt, "read", throw=True)

	rows = frappe.get_all(
		"Page Script",
		filters={"dt": dt, "view": view, "enabled": 1},
		fields=["name", "script", "module"],
		order_by=PAGE_SCRIPT_ORDER,
	)
	return {
		"scripts": [
			{"name": row.name, "script": row.script or ""}
			for row in rows
			if not is_module_disabled(row.module)
		],
		"can_write": bool(frappe.has_permission("Page Script", "write")),
	}


@frappe.whitelist(methods=["POST"])
def reorder(dt: str, view: str, names: list[str]) -> None:
	"""Renumber `names` densely, 1..n, in the order the author dragged them into.

	One method rather than N saves from the editor: dense renumbering is N writes, and
	N separate requests can tear — a connection dropped halfway leaves the list
	numbered 1,2,3,3,4. One method is one transaction, all or nothing.
	"""
	_validate_target(dt, view)
	if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
		frappe.throw(_("Scripts must be a list of names"))
	frappe.has_permission("Page Script", "write", throw=True)
	_reject_names_that_are_not_this_doctypes(dt, view, names)

	for position, name in enumerate(names, start=1):
		# `set_value`, not `save`: `run_order` is a bare ordinal with no validation and
		# no state transition, and skipping the document lifecycle is what collapses N
		# `page_script_changed` broadcasts and N Version rows into none. `modified` is
		# left alone so the editor's per-script optimistic lock keeps meaning "this
		# script's text changed", not "a sibling moved".
		frappe.db.set_value("Page Script", name, "run_order", position, update_modified=False)

	# One broadcast for the whole drag, and no commit — Frappe owns the transaction,
	# which is the thing making the renumbering atomic.
	frappe.publish_realtime(PAGE_SCRIPT_CHANGED, {"dt": dt, "view": view}, after_commit=True)


def _validate_target(dt: str, view: str) -> None:
	# Belt and braces: the whitelist decorator already rejects a non-str `dt`, and one
	# reaching get_all would be a filter operator (`["!=", ""]`) that reads every
	# doctype's scripts past the permission check.
	if not isinstance(dt, str):
		frappe.throw(_("Document Type must be a name"))
	if view not in PAGE_SCRIPT_VIEWS:
		frappe.throw(_("Invalid Page Script view: {0}").format(view))


def _reject_names_that_are_not_this_doctypes(dt: str, view: str, names: list[str]) -> None:
	"""No benign path sends a duplicate, or a name belonging to another doctype's list.

	A *missing* name is benign and deliberately tolerated: that is the ordinary outcome
	of a concurrent create, and the newcomer keeps the `run_order` it was created with
	— max+1 of the older numbering — so it sorts last, where a just-created script
	belongs. Rejecting would surface a stale-list error on a drag.
	"""
	if len(set(names)) != len(names):
		frappe.throw(_("A script cannot appear twice in the run order"))

	known = set(frappe.get_all("Page Script", filters={"dt": dt, "view": view}, pluck="name"))
	unknown = sorted(set(names) - known)
	if unknown:
		frappe.throw(_("Not Page Scripts of {0}: {1}").format(dt, ", ".join(unknown)))
