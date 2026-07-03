# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import re

import frappe
import frappe.utils
from frappe import _
from frappe.model.document import Document
from frappe.utils.jinja import validate_template
from frappe.utils.print_format_generator import download_pdf, get_html


class PrintFormat(Document):
	_DOCTYPE_NAME = "Print Format"

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
		label_color: DF.Color | None
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
		preview_image: DF.AttachImage | None
		print_format_builder: DF.Check
		print_format_builder_beta: DF.Check
		print_format_for: DF.Literal["DocType", "Report"]
		print_format_type: DF.Literal["Jinja", "JS"]
		raw_commands: DF.Code | None
		raw_printing: DF.Check
		report: DF.Link | None
		show_section_headings: DF.Check
		standard: DF.Literal["No", "Yes"]
		value_color: DF.Color | None
	# end: auto-generated types

	def onload(self):
		templates = frappe.get_all(
			"Print Format Field Template",
			fields=["template", "field", "name"],
			or_filters=[
				["document_type", "=", self.doc_type],
				["document_type", "is", "not set"],
			],
			order_by="document_type desc",
		)
		self.set_onload("print_templates", templates)

	def before_save(self):
		if self.print_format_for == "Report":
			self.custom_format = 1

		# New non-custom formats default to builder beta + Chrome
		if self.is_new() and not self.custom_format:
			self.print_format_builder_beta = 1

		if self.print_format_builder_beta and not self.custom_format:
			self.pdf_generator = "chrome"

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

		if self.html and self.print_format_type != "JS":
			validate_template(self.html)

		if self.custom_format and self.raw_printing and not self.raw_commands:
			frappe.throw(_("{0} are required").format(frappe.bold(_("Raw Commands"))), frappe.MandatoryError)

		if self.custom_format and not self.html and not self.raw_printing:
			frappe.throw(_("{0} is required").format(frappe.bold(_("HTML"))), frappe.MandatoryError)

		if self.print_format_for == "Report" and not self.report:
			frappe.throw(_("{0} is required").format(frappe.bold(_("Report"))), frappe.MandatoryError)

		self.validate_colors()

	def validate_colors(self):
		for fieldname in ("label_color", "value_color"):
			value = self.get(fieldname)
			if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
				frappe.throw(
					_("{0} must be a hex color code like #1a5fb4").format(
						frappe.bold(_(self.meta.get_label(fieldname)))
					)
				)

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

	def on_update(self):
		if hasattr(self, "old_doc_type") and self.old_doc_type:
			frappe.clear_cache(doctype=self.old_doc_type)
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)

		self.export_doc()
		self.enqueue_preview_generation()

	def enqueue_preview_generation(self):
		"""Refresh the preview image in the background so saving the format isn't blocked by
		the (slow) Chromium render. Deduplicated so rapid saves don't pile up renders."""
		if (
			frappe.flags.in_import
			or frappe.flags.in_migrate
			or frappe.flags.in_install
			or frappe.flags.in_patch
			or frappe.in_test
		):
			return
		if self.print_format_for != "DocType" or not self.doc_type:
			return

		frappe.enqueue(
			generate_preview,
			queue="short",
			enqueue_after_commit=True,
			job_id=f"print_format_preview::{self.name}",
			deduplicate=True,
			name=self.name,
		)

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

		return export_module_json(self, self.standard == "Yes", self.module, create_init=False)

	def on_trash(self):
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)


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


def printable_sample(doctype: str) -> str | None:
	"""Most recent document the user can read AND print. Submittable doctypes only
	reliably print submitted docs (draft/cancelled hit the printview guards), so
	restrict to those; otherwise any latest doc works."""
	filters = {"docstatus": 1} if frappe.get_meta(doctype).is_submittable else {}
	sample = frappe.get_list(doctype, filters=filters, limit=1, order_by="modified desc", pluck="name")
	return sample[0] if sample else None


def generate_preview(name: str) -> str | None:
	"""Render this format against a sample document, screenshot the HTML via the
	bundled Chromium, and store the result in the format's `preview_image` field.

	Uses `db_set` rather than `save` so it works for standard formats too (whose
	`validate` blocks saving) and skips the full validation cycle. Returns the new
	image URL, or None when there's no printable sample to render against."""
	doc = frappe.get_doc("Print Format", name)

	sample_name = printable_sample(doc.doc_type)
	if not sample_name:
		return

	from frappe.utils.file_manager import save_file
	from frappe.utils.preview import get_preview_from_html

	try:
		html = frappe.get_print(doc.doc_type, sample_name, name)
		# 850px ≈ 8.3in at 96dpi — matches the print sheet width so margin:auto
		# centers correctly and the screenshot captures the full page width.
		image = get_preview_from_html(html, format="webp", width=850)
	except Exception:
		frappe.local.message_log = []
		frappe.log_error(f"Print format preview generation failed: {name}")
		return None

	# Drop the previous preview file (if any) before storing the fresh one.
	# Use ignore_permissions=True because the file may have been generated by a different
	# user and the current caller might not own it — but only delete files that are
	# actually attached to this Print Format to prevent preview_image from being used
	# to delete arbitrary File records.
	if doc.preview_image:
		old = frappe.db.get_value(
			"File",
			{"file_url": doc.preview_image, "attached_to_doctype": "Print Format", "attached_to_name": name},
			"name",
		)
		if old:
			frappe.delete_doc("File", old, ignore_permissions=True, delete_permanently=True)

	fname = f"pf-preview-{frappe.generate_hash(length=10)}.webp"
	file = save_file(fname, image, "Print Format", name, is_private=1)
	# Don't bump `modified` — generating a preview isn't a content edit. Otherwise the
	# background refresh would stale-date an open form and break its next save with a
	# timestamp mismatch.
	doc.db_set("preview_image", file.file_url, update_modified=False)
	return file.file_url
