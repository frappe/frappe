# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import os
import re

import frappe
from frappe import _
from frappe.app_state import is_module_disabled
from frappe.model.document import Document

RECORD_PAGE_VIEWS = ("Record",)
CLIENT_SCRIPT_CHANGED = "client_script_changed"
# `run_order` is a sort key, not a unique one; `creation` breaks the ties.
RECORD_SCRIPT_ORDER = "run_order asc, creation asc"
CLASS_LIST = ("assets", "frappe", "frontend", "classes.json")
# Only text handed to `class` is read as class names; prose is not.
CLASS_CONTEXTS = (
	re.compile(r"""\bclass(?:Name)?\s*=\s*\\?(["'])(?P<text>.*?)\\?\1""", re.S),
	re.compile(r"""\bclass(?:Name)?\s*:\s*(["'`])(?P<text>.*?)\1""", re.S),
	re.compile(r"\bclassList\.(?:add|remove|toggle|replace)\((?P<text>[^)]*)\)"),
)
CLASS_WORD = re.compile(r"[!-]?[A-Za-z](?:[\w:./%-]|\[[^\]\s]*\])*")


class ClientScript(Document):
	_DOCTYPE_NAME = "Client Script"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		dt: DF.Link
		enabled: DF.Check
		module: DF.Link | None
		run_order: DF.Int
		script: DF.Code | None
		view: DF.Literal["List", "Form", "Record"]
	# end: auto-generated types

	def validate(self):
		self.warn_on_unknown_classes()

	def on_update(self):
		frappe.clear_cache(doctype=self.dt)
		self.notify_record_pages()

	def warn_on_unknown_classes(self):
		"""Name every class the script uses that the desk stylesheet has no rule for; never block."""
		if self.view not in RECORD_PAGE_VIEWS or not self.script:
			return
		if not (self.is_new() or self.has_value_changed("script")):
			return
		known = read_class_list()
		if known is None:
			return
		unknown = sorted(set(class_words(self.script)) - known)
		if unknown:
			frappe.msgprint(
				_(
					"These classes have no style in the desk, so they will not change how the page looks: {0}. Use classes from the desk palette."
				).format(", ".join(unknown)),
				title=_("Classes with no style"),
				indicator="orange",
			)

	def on_trash(self):
		frappe.clear_cache(doctype=self.dt)
		self.notify_record_pages()

	def notify_record_pages(self):
		if self.view not in RECORD_PAGE_VIEWS:
			return
		frappe.publish_realtime(  # nosemgrep
			CLIENT_SCRIPT_CHANGED, {"dt": self.dt, "view": self.view}, after_commit=True
		)


@frappe.whitelist()
def get_client_scripts(dt: str, view: str = "Record"):
	"""Return the enabled scripts a Record page of `dt` runs, in run order."""
	validate_target(dt, view)
	frappe.has_permission(dt, "read", throw=True)

	rows = frappe.get_all(
		"Client Script",
		filters={"dt": dt, "view": view, "enabled": 1},
		fields=["name", "script", "module"],
		order_by=RECORD_SCRIPT_ORDER,
	)
	return {
		"scripts": [
			{"name": row.name, "script": row.script or ""}
			for row in rows
			if not is_module_disabled(row.module)
		],
		"can_write": bool(frappe.has_permission("Client Script", "write")),
	}


@frappe.whitelist(methods=["POST"])
def reorder(dt: str, view: str, names: list[str]) -> None:
	"""Renumber `names` densely from 1 in the given order, in one transaction."""
	validate_target(dt, view)
	if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
		frappe.throw(_("Scripts must be a list of names"))
	frappe.has_permission("Client Script", "write", throw=True)
	reject_foreign_names(dt, view, names)

	# `modified` stays put: the editor's lock on it means "this script's text changed".
	positions = {name: {"run_order": position} for position, name in enumerate(names, start=1)}
	frappe.db.bulk_update("Client Script", positions, update_modified=False)

	frappe.publish_realtime(CLIENT_SCRIPT_CHANGED, {"dt": dt, "view": view}, after_commit=True)  # nosemgrep


def validate_target(dt: str, view: str) -> None:
	# A non-str `dt` would reach `get_all` as a filter operator and read every doctype's scripts.
	if not isinstance(dt, str):
		frappe.throw(_("Document Type must be a name"))
	if view not in RECORD_PAGE_VIEWS:
		frappe.throw(_("Client Scripts for the {0} view are not served to a record page").format(view))


def reject_foreign_names(dt: str, view: str, names: list[str]) -> None:
	"""Refuse a duplicate or a name outside this doctype's list; a missing name is tolerated."""
	if len(set(names)) != len(names):
		frappe.throw(_("A script cannot appear twice in the run order"))

	known = set(frappe.get_all("Client Script", filters={"dt": dt, "view": view}, pluck="name"))
	unknown = sorted(set(names) - known)
	if unknown:
		frappe.throw(_("Not Client Scripts of {0}: {1}").format(dt, ", ".join(unknown)))


def read_class_list() -> set[str] | None:
	"""The classes the desk build generated, or None when no build has written a readable list."""
	try:
		with open(class_list_path()) as file:
			names = json.load(file)
	except (OSError, ValueError):
		return None
	if not isinstance(names, list):
		return None
	return {name for name in names if isinstance(name, str)}


def class_list_path() -> str:
	return os.path.join(frappe.local.sites_path, *CLASS_LIST)


def class_words(script: str) -> list[str]:
	"""Utility-shaped words (a hyphen or a variant colon) where the script names classes."""
	words = []
	for context in CLASS_CONTEXTS:
		for match in context.finditer(script):
			words += [w for w in CLASS_WORD.findall(match.group("text")) if "-" in w or ":" in w]
	return words
