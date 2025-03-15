import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader, PdfWriter

import frappe
from frappe.core.doctype.file.utils import get_local_image, get_web_image
from frappe.model.document import Document
from frappe.utils.data import to_markdown
from frappe.utils.pdf import get_file_data_from_writer


def print_with_typst(
	doctype, name, print_format, as_pdf, doc, output: PdfWriter | None = None, password=None
):
	if not doc:
		doc = frappe.get_doc(doctype, name)

	template = frappe.db.get_value("Print Format", print_format, "raw_commands")
	temp_dirname = Path("/tmp") / str(uuid4())
	temp_dirname.mkdir(parents=True, exist_ok=False)

	template_path = temp_dirname / "main.typ"
	template_path.write_text(template)

	doc_dict = get_resolved_dict(doc, temp_dirname)
	json_path = temp_dirname / "doc.json"
	json_path.write_text(frappe.as_json(doc_dict))

	# run command
	subprocess.run(["typst", "compile", template_path])

	output_path = temp_dirname / "main.pdf"
	if not output_path.exists():
		raise Exception("Failed to generate PDF")

	reader = PdfReader(output_path)

	if output:
		output.append_pages_from_reader(reader)
		return output

	writer = PdfWriter()
	writer.append_pages_from_reader(reader)

	if password:
		writer.encrypt(password)

	shutil.rmtree(temp_dirname)

	return get_file_data_from_writer(writer)


def get_resolved_dict(doc: "Document", temp_dirname: Path, depth: int = 0) -> dict:
	"""Resolve links and return as nested JSON"""
	doc_dict = doc.as_dict()
	for fieldname, value in doc_dict.items():
		if value is None:
			continue

		df = doc.meta.get_field(fieldname)
		if not df:
			continue

		if df.fieldtype == "Link" and df.options != "DocType" and depth < 1:
			doc_dict[df.fieldname] = (
				get_resolved_dict(frappe.get_doc(df.options, value), temp_dirname, depth + 1) if value else {}
			)
		if df.fieldtype == "Dynamic Link" and doc[df.options] and depth < 1:
			doc_dict[df.fieldname] = (
				get_resolved_dict(frappe.get_doc(doc[df.options], value), temp_dirname, depth + 1)
				if value
				else {}
			)
		if df.fieldtype in ("Table", "Table MultiSelect") and depth < 1:
			for child_row in value:
				child_row.update(
					get_resolved_dict(
						doc.get(fieldname, {"name": child_row["name"]})[0], temp_dirname, depth + 1
					)
				)
		if df.fieldtype in ("Date", "Datetime", "Float", "Int", "Currency", "Duration"):
			doc_dict[df.fieldname] = {
				"value": value,
				"formatted": doc.get_formatted(fieldname),
			}
		if df.fieldtype == "Attach Image" and value:
			if value.startswith(("/files", "/private/files")):
				image, filename, extn = get_local_image(value)
			else:
				image, filename, extn = get_web_image(value)

			image_path = (temp_dirname / filename.lstrip(os.sep)).with_suffix(f".{extn}")
			image_path.parent.mkdir(parents=True, exist_ok=True)
			image.save(image_path)
			doc_dict[df.fieldname] = str(image_path.relative_to(temp_dirname))
		if df.fieldtype in ("Text Editor"):
			doc_dict[df.fieldname] = to_markdown(value)

	return doc_dict
