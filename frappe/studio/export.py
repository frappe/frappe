import os
import shutil
from pathlib import Path

import frappe
from frappe.modules import scrub
from frappe.modules.export_file import strip_default_fields


def write_document_file(doc, folder=None):
	doc_export = doc.as_dict(no_nulls=True)
	doc.run_method("before_export", doc_export)
	doc_export = strip_default_fields(doc, doc_export)

	fname = scrub(doc_export.name)
	path = os.path.join(folder, f"{fname}.json")
	if Path(path).resolve().is_relative_to(Path(frappe.get_site_path()).resolve()):
		frappe.throw("Invalid export path: " + Path(path).as_posix())
	with open(path, "w+") as txtfile:
		txtfile.write(frappe.as_json(doc_export) + "\n")
	print(f"Wrote document file for {doc.doctype} {doc.name} at {path}")


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
