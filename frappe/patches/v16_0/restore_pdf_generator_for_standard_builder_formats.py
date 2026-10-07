import json

import frappe
from frappe.modules.import_file import get_file_path


def execute():
	"""Standard builder formats were pinned to WeasyPrint along with user-made ones; put
	them back on the renderer their app ships."""
	for row in frappe.get_all(
		"Print Format",
		filters={"standard": "Yes", "print_format_builder_beta": 1, "pdf_generator": "WeasyPrint"},
		fields=["name", "module"],
	):
		pdf_generator = get_shipped_pdf_generator(row)
		if pdf_generator and pdf_generator != "WeasyPrint":
			frappe.db.set_value(
				"Print Format", row.name, "pdf_generator", pdf_generator, update_modified=False
			)


def get_shipped_pdf_generator(row):
	if not row.module:
		return
	try:
		with open(get_file_path(row.module, "Print Format", row.name), encoding="utf-8") as f:
			doc = json.load(f)
	except (frappe.DoesNotExistError, OSError, ValueError):
		return
	if isinstance(doc, dict):
		return doc.get("pdf_generator") or frappe.get_meta("Print Format").get_field("pdf_generator").default
