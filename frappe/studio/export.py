import os
import shutil
from pathlib import Path

import frappe
from frappe.modules import scrub
from frappe.modules.export_file import strip_default_fields


def write_document_file(doc, folder=None, exclude_fields=None):
	doc_export = doc.as_dict(no_nulls=True)
	doc.run_method("before_export", doc_export)
	doc_export = strip_default_fields(doc, doc_export)

	# Fields written to a companion file (e.g. a Code field exported as .js) are dropped from JSON.
	for field in exclude_fields or []:
		doc_export.pop(field, None)

	fname = scrub(doc_export.name)
	path = os.path.join(folder, f"{fname}.json")
	if Path(path).resolve().is_relative_to(Path(frappe.get_site_path()).resolve()):
		frappe.throw("Invalid export path: " + Path(path).as_posix())
	with open(path, "w+") as txtfile:
		txtfile.write(frappe.as_json(doc_export) + "\n")
	print(f"Wrote document file for {doc.doctype} {doc.name} at {path}")


def write_code_file(doc, folder, code_field, extension, filename=None):
	"""Export a doc's Code field to a companion file (e.g. <name>.js) next to its JSON,
	so the source is readable and diffable on disk instead of buried in JSON.

	`filename` overrides the stem (without extension) so the code file can match its sibling
	JSON's name (e.g. a page's <scrub(page_title)>.ts beside <scrub(page_title)>.json)."""
	fname = filename or scrub(doc.name)
	path = os.path.join(folder, f"{fname}.{extension}")
	if Path(path).resolve().is_relative_to(Path(frappe.get_site_path()).resolve()):
		frappe.throw("Invalid export path: " + Path(path).as_posix())
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


def parse_json(field):
	if field and isinstance(field, str):
		return frappe.parse_json(field)
	return


def remove_null_fields(docdict):
	"""remove null and empty fields"""
	to_remove = []
	for attr, value in docdict.items():
		if isinstance(value, list):
			for v in value:
				if isinstance(v, dict):
					remove_null_fields(v)
		elif not value:
			to_remove.append(attr)

	for attr in to_remove:
		del docdict[attr]
