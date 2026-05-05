# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import os
import shutil
from pathlib import Path

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.modules.export_file import (
	get_custom_module_path,
	get_module_path,
	scrub_dt_dn,
)
from frappe.utils.jinja import validate_template
from frappe.utils.weasyprint import download_pdf, get_html


class PrintFormat(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		absolute_value: DF.Check
		align_labels_right: DF.Check
		css: DF.Code | None
		custom_format: DF.Check
		default_print_language: DF.Link | None
		disabled: DF.Check
		doc_type: DF.Link | None
		font: DF.Data | None
		font_size: DF.Int
		format_data: DF.Code | None
		html: DF.Code | None
		line_breaks: DF.Check
		margin_bottom: DF.Float
		margin_left: DF.Float
		margin_right: DF.Float
		margin_top: DF.Float
		module: DF.Link | None
		page_number: DF.Literal[
			"Hide", "Top Left", "Top Center", "Top Right", "Bottom Left", "Bottom Center", "Bottom Right"
		]
		pdf_generator: DF.Literal["wkhtmltopdf", "chrome"]
		print_format_builder: DF.Check
		print_format_builder_beta: DF.Check
		print_format_for: DF.Literal["DocType", "Report"]
		print_format_type: DF.Literal["Jinja", "JS"]
		raw_commands: DF.Code | None
		raw_printing: DF.Check
		report: DF.Link | None
		show_section_headings: DF.Check
		standard: DF.Literal["No", "Yes"]
	# end: auto-generated types

	def onload(self):
		templates = frappe.get_all(
			"Print Format Field Template",
			fields=["template", "field", "name"],
			filters={"document_type": self.doc_type},
		)
		self.set_onload("print_templates", templates)
		self.load_content_from_files()

	def load_content_from_files(self):
		"""Hydrate file-backed content in-memory for frontend actions."""
		if self.standard != "Yes" or not self.custom_format:
			return

		if self.raw_printing:
			self.raw_commands = self.get_format_raw_commands()
		else:
			self.html = self.get_format_html()
			self.css = self.get_format_css()

	def before_save(self):
		if self.print_format_for == "Report":
			self.custom_format = 1

		if frappe.conf.developer_mode:
			was_standard = (self.get_doc_before_save() or {}).get("standard")

			if self.standard == "Yes":
				self.export_to_files()

			if was_standard == "Yes" and self.standard != "Yes":
				self.import_from_files()

	def get_html(self, docname, letterhead=None):
		return get_html(self.doc_type, docname, self.name, letterhead)

	def download_pdf(self, docname, letterhead=None):
		return download_pdf(self.doc_type, docname, self.name, letterhead)

	def validate(self):
		if (
			self.standard == "Yes"
			and not frappe.local.conf.get("developer_mode")
			and not frappe.flags.in_migrate
			and not frappe.flags.in_install
			and not frappe.in_test
		):
			frappe.throw(frappe._("Standard Print Format cannot be updated"))

		# old_doc_type is required for clearing item cache
		self.old_doc_type = frappe.db.get_value("Print Format", self.name, "doc_type")

		self.extract_images()

		if not self.module:
			doc_type = "DocType" if self.print_format_for == "DocType" else "Report"
			document_name = self.doc_type if self.print_format_for == "DocType" else self.report
			self.module = frappe.db.get_value(doc_type, document_name, "module")

		format_html = None
		if self.custom_format and not self.raw_printing:
			format_html = self.get_format_html()
			if format_html and self.print_format_type != "JS":
				validate_template(format_html)

		if (
			self.custom_format
			and self.raw_printing
			and not self.get_format_raw_commands()
			and self.standard != "Yes"
		):
			frappe.throw(_("{0} are required").format(frappe.bold(_("Raw Commands"))), frappe.MandatoryError)

		if self.custom_format and not self.raw_printing and not format_html and self.standard != "Yes":
			frappe.throw(_("{0} is required").format(frappe.bold(_("HTML"))), frappe.MandatoryError)

		if self.print_format_for == "Report" and not self.report:
			frappe.throw(_("{0} is required").format(frappe.bold(_("Report"))), frappe.MandatoryError)

	def extract_images(self):
		from frappe.core.doctype.file.utils import extract_images_from_html

		if self.print_format_builder_beta:
			return

		if self.format_data:
			data = json.loads(self.format_data)
			for df in data:
				if df.get("fieldtype") and df["fieldtype"] in ("HTML", "Custom HTML") and df.get("options"):
					df["options"] = extract_images_from_html(self, df["options"])
			self.format_data = json.dumps(data)

	def export_to_files(self):
		"""Export Print Format to a new folder.

		Doc is exported as JSON. The content of the `html`, `css` and
		`raw_commands` fields are written into separate files.
		"""
		if not self.custom_format:
			return

		if self.raw_printing:
			raw_commands = self.raw_commands
			self.raw_commands = None
			self.create_format_file(raw_commands, "txt")
			return

		html, css = self.html, self.css
		self.html = None
		self.css = None
		self.create_format_file(html, "html")
		self.create_format_file(css, "css")

	def import_from_files(self, overwrite_existing=False):
		if self.custom_format:
			if self.raw_printing:
				raw_commands = self._get_format_file_content("txt")
				if raw_commands is not None and (overwrite_existing or self.raw_commands is None):
					self.raw_commands = raw_commands
			else:
				html = self._get_format_file_content("html")
				if html is not None and (overwrite_existing or self.html is None):
					self.html = html
				css = self._get_format_file_content("css")
				if css is not None and (overwrite_existing or self.css is None):
					self.css = css
		folder = self.get_format_folder()
		if folder and folder.exists():
			shutil.rmtree(folder)

	def create_format_file(self, content, extension):
		"""Touch a code file for the Print Format and add existing content, if any."""
		if self.standard != "Yes":
			return

		path = self.get_format_path(extension)
		if path is None or path.exists():
			return

		path.parent.mkdir(parents=True, exist_ok=True)

		if content:
			path.write_text(content)
		else:
			path.touch()

	def get_format_folder(self):
		"""Return the absolute path to the print format's folder."""
		module = self._get_module_for_files()
		if not module:
			return None

		if frappe.get_cached_value("Module Def", module, "custom"):
			try:
				module_path = get_custom_module_path(module)
			except frappe.ValidationError:
				return None
		else:
			module_path = get_module_path(module)

		doctype, docname = scrub_dt_dn(self.doctype, self.name)
		return Path(module_path) / doctype / docname

	def get_format_path(self, extension):
		"""Return the absolute path to a print format code file."""
		folder = self.get_format_folder()
		if not folder:
			return None

		file_name = f"{frappe.scrub(self.name)}.{extension}"
		return folder / file_name

	def get_format_html(self):
		return self._get_format_content("html", "html")

	def get_format_css(self):
		return self._get_format_content("css", "css")

	def get_format_raw_commands(self):
		return self._get_format_content("txt", "raw_commands")

	def _get_format_content(self, extension, fieldname):
		if self.standard == "Yes":
			content = self._get_format_file_content(extension)
			if content is not None:
				return content
		return self.get(fieldname)

	def _get_module_for_files(self):
		if self.module:
			return self.module

		doc_type = "DocType" if self.print_format_for == "DocType" else "Report"
		document_name = self.doc_type if self.print_format_for == "DocType" else self.report
		return frappe.db.get_value(doc_type, document_name, "module")

	def _get_format_file_content(self, extension):
		path = self.get_format_path(extension)
		if path and path.exists():
			return path.read_text()
		return None

	def on_update(self):
		if hasattr(self, "old_doc_type") and self.old_doc_type:
			frappe.clear_cache(doctype=self.old_doc_type)
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)

		self.export_doc()

	def after_rename(self, old: str, new: str, *args, **kwargs):
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)

		# update property setter default_print_format if set
		frappe.db.set_value(
			"Property Setter",
			{
				"doctype_or_field": "DocType",
				"doc_type": self.doc_type,
				"property": "default_print_format",
				"value": old,
			},
			"value",
			new,
		)

	def export_doc(self):
		from frappe.modules.utils import export_module_json

		return export_module_json(self, self.standard == "Yes", self.module)

	def on_trash(self):
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)
		if frappe.conf.developer_mode and self.standard == "Yes":
			folder = self.get_format_folder()
			if folder and folder.exists():
				shutil.rmtree(folder)


@frappe.whitelist()
def make_default(name: str):
	"""Set print format as default"""
	print_format = frappe.get_doc("Print Format", name)
	print_format.check_permission("write")

	doctype = frappe.get_doc("DocType", print_format.doc_type)
	if doctype.custom:
		doctype.default_print_format = name
		doctype.save()
	else:
		# "Customize form"
		frappe.make_property_setter(
			{
				"doctype_or_field": "DocType",
				"doctype": print_format.doc_type,
				"property": "default_print_format",
				"value": name,
			}
		)

	frappe.msgprint(
		frappe._("{0} is now default print format for {1} doctype").format(
			frappe.bold(name), frappe.bold(print_format.doc_type)
		)
	)


@frappe.whitelist()
def get_print_format_file_content(name: str) -> dict:
	if not name:
		return {}

	try:
		print_format = frappe.get_doc("Print Format", name)
	except frappe.DoesNotExistError:
		return {}

	print_format.check_permission("read")
	return {
		"html": print_format.get_format_html(),
		"css": print_format.get_format_css(),
		"raw_commands": print_format.get_format_raw_commands(),
	}


@frappe.whitelist()
def get_print_format_content(name: str) -> dict:
	if not name:
		return {}

	try:
		print_format = frappe.get_doc("Print Format", name)
	except frappe.DoesNotExistError:
		return {}

	if print_format.print_format_for == "DocType":
		frappe.has_permission(print_format.doc_type, "print", throw=True)

	if print_format.print_format_for == "Report":
		report = frappe.get_doc("Report", print_format.report)
		if not report.is_permitted():
			frappe.throw(
				_("You don't have access to Report: {0}").format(_(report.name)),
				frappe.PermissionError,
			)

	if print_format.disabled:
		return {}

	return {
		"html": print_format.get_format_html(),
		"css": print_format.get_format_css(),
	}
