import os
import shutil
from pathlib import Path

import frappe
from frappe import _
from frappe.modules import scrub
from frappe.modules.export_file import strip_default_fields
from frappe.studio.sync_json import cache_synced_file_hash
from frappe.studio.utils import validate_installed_app

PRESERVED_EMPTY_PROPERTIES = frozenset({"componentProps", "componentSlots"})
SYNC_FLAGS = ("in_import", "in_migrate", "in_install", "in_uninstall", "in_patch")


def write_document_file(doc, folder=None, exclude_fields=None):
	doc_export = doc.as_dict(no_nulls=True)
	doc.run_method("before_export", doc_export)
	doc_export = strip_default_fields(doc, doc_export)
	# Fields written to a companion file (e.g. a Code field exported as .js) are dropped from JSON.
	remove_empty_values(doc_export)
	for field in exclude_fields or []:
		doc_export.pop(field, None)

	fname = scrub(doc_export.name)
	path = os.path.join(folder, f"{fname}.json")
	if Path(path).resolve().is_relative_to(Path(frappe.get_site_path()).resolve()):
		frappe.throw(_("Invalid export path: {0}").format(Path(path).as_posix()))
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
	with open(path, "w+") as txtfile:
		txtfile.write(frappe.as_json(doc_export) + "\n")
	cache_synced_file_hash(path)
	print(f"Wrote document file for {doc.doctype} {doc.name} at {path}")


def write_code_file(doc, folder, code_field, extension, filename=None):
	"""Export a doc's Code field to a companion file (e.g. <name>.js) next to its JSON,
	so the source is readable and diffable on disk instead of buried in JSON.

	`filename` overrides the stem (without extension) so the code file can match its sibling
	JSON's name (e.g. a page's <scrub(page_title)>.ts beside <scrub(page_title)>.json)."""
	fname = filename or scrub(doc.name)
	path = os.path.join(folder, f"{fname}.{extension}")
	if Path(path).resolve().is_relative_to(Path(frappe.get_site_path()).resolve()):
		frappe.throw(_("Invalid export path: {0}").format(Path(path).as_posix()))
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
	with open(path, "w+") as codefile:
		codefile.write(doc.get(code_field) or "")
	print(f"Wrote {extension} file for {doc.doctype} {doc.name} at {path}")


def delete_folder(path=None):
	if path and os.path.exists(path):
		shutil.rmtree(path, ignore_errors=True)


def delete_file(path, *joins):
	if not path:
		return
	path = os.path.join(path, *joins)
	if os.path.exists(path):
		os.remove(path)


def can_export(doc) -> bool:
	"""Check if exporting is allowed for the doc based on the current site flags"""
	return (
		doc.is_standard
		and frappe.conf.developer_mode
		and not frappe.flags.in_install
		and not frappe.flags.in_uninstall
		and not frappe.flags.in_import
	)


def validate_standard_app_change(doc):
	"""Block standard apps, pages and component edits outside developer mode.
	Allow changes only during migration, installation, and patches (which sync app's files)."""
	if frappe.conf.developer_mode:
		return
	previous = doc.get_doc_before_save()
	# clearing is_standard changes a standard doc too
	if not (doc.is_standard or (previous and previous.is_standard)):
		return
	if any(frappe.flags.get(flag) for flag in SYNC_FLAGS):
		return
	frappe.throw(
		_("Standard apps can only be edited in developer mode."),
		frappe.PermissionError,
		title=_("Not Allowed"),
	)


def validate_frappe_app(doc):
	"""Synced docs are exempt: they carry the app being installed, which get_installed_apps
	does not list until the install finishes."""
	if not doc.frappe_app or any(frappe.flags.get(flag) for flag in SYNC_FLAGS):
		return
	validate_installed_app(doc.frappe_app)


def parse_json(field):
	if field and isinstance(field, str):
		return frappe.parse_json(field)
	return


def remove_empty_values(docdict):
	"""Remove empty fields from documents, child rows, block children, and slot content."""
	to_remove = []
	for attr, value in docdict.items():
		if attr == "componentSlots" and isinstance(value, dict):
			remove_empty_values_from_slots(value)
		if attr in PRESERVED_EMPTY_PROPERTIES:
			continue

		if isinstance(value, list):
			for item in value:
				if isinstance(item, dict):
					remove_empty_values(item)
			if not value:
				to_remove.append(attr)
		elif isinstance(value, dict):
			if not value:
				to_remove.append(attr)
		elif value is None or value == "":
			to_remove.append(attr)

	for attr in to_remove:
		del docdict[attr]


def remove_empty_values_from_slots(slots):
	"""Prune blocks inside slot content; the slots themselves are kept as-is."""
	for slot in slots.values():
		if isinstance(slot, dict) and isinstance(slot.get("slotContent"), list):
			for block in slot["slotContent"]:
				if isinstance(block, dict):
					remove_empty_values(block)
