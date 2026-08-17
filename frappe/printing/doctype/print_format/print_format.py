# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import re
from datetime import datetime

import frappe
import frappe.utils
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import delete_property_setter
from frappe.model.document import Document
from frappe.utils.jinja import validate_template
from frappe.utils.print_format_generator import download_pdf, get_html

#: The fields the builder may hold in `draft_data`. Everything the builder can edit
#: belongs here — a field left out stays live, so a margin would apply instantly
#: while the layout waited for Save & Apply.
BUILDER_DRAFT_FIELDS = (
	"format_data",
	"font",
	"font_size",
	"page_number",
	"show_label_colon",
	"margin_top",
	"margin_bottom",
	"margin_left",
	"margin_right",
	"label_color",
	"value_color",
	# written once when a classic format is converted on open
	"classic_format_data",
	"print_format_builder",
	"print_format_builder_beta",
	"pdf_generator",
)


class PrintFormat(Document):
	_DOCTYPE_NAME = "Print Format"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		absolute_value: DF.Check
		align_labels_right: DF.Check
		classic_format_data: DF.Code | None
		css: DF.Code | None
		custom_format: DF.Check
		default_print_language: DF.Link | None
		disabled: DF.Check
		doc_type: DF.Link | None
		draft_data: DF.Code | None
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
		pdf_generator: DF.Literal["wkhtmltopdf", "chrome", "Typst"]
		print_format_builder: DF.Check
		print_format_builder_beta: DF.Check
		print_format_for: DF.Literal["DocType", "Report"]
		print_format_type: DF.Literal["Jinja", "JS"]
		raw_commands: DF.Code | None
		raw_printing: DF.Check
		report: DF.Link | None
		show_label_colon: DF.Check
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

		# standard formats render from their app's .html template and Print Designer
		# formats from their own renderer — the beta renderer can read neither
		if (
			self.is_new()
			and not self.custom_format
			and self.standard != "Yes"
			and not self.get("print_designer")
		):
			self.print_format_builder_beta = 1

		if self.print_format_builder_beta and not self.custom_format and self.pdf_generator != "Typst":
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
		self.validate_conditions()
		self.validate_typst_renderer()

	def validate_typst_renderer(self):
		"""Refuse to save a Typst-flagged format that Typst cannot render — the
		blockers name exactly what to remove, at edit time instead of print time."""
		from frappe.utils.typst_emitter import has_typst_blocks, typst_blockers

		try:
			layout = frappe.parse_json(self.format_data) if self.format_data else {}
		except Exception:
			layout = {}
		if not isinstance(layout, dict):
			layout = {}

		if self.pdf_generator != "Typst":
			# the mirror gate: raw Typst markup can't render anywhere else
			if has_typst_blocks(layout):
				frappe.throw(
					_("This format uses a Typst block, so its PDF Renderer must be Typst."),
					title=_("Typst block requires the Typst renderer"),
				)
			return
		blockers = typst_blockers(self, layout)
		if blockers:
			frappe.throw(
				_("This format cannot use the Typst renderer: {0}").format(", ".join(blockers)),
				title=_("Typst renderer unavailable"),
			)
		self._validate_typst_block_markup(layout)

	def _validate_typst_block_markup(self, layout):
		"""Compile each raw Typst block on save so a typo fails here, with the
		block named, instead of breaking every print later."""
		from frappe.utils.jinja import get_jenv
		from frappe.utils.typst_emitter import (
			_walk,
			compile_typst_source,
			has_jinja,
			has_typst_blocks,
			render_typst_template,
		)

		if not has_typst_blocks(layout):
			return
		try:
			import typst
		except ImportError:
			return
		sample_doc = None
		sample_loaded = False
		for where, df in _walk(layout):
			markup = (df.get("typst") or "").strip() if df.get("fieldtype") == "Typst" else ""
			if not markup:
				continue
			if has_jinja(markup):
				if not sample_loaded:
					sample_doc = self._typst_sample_doc()
					sample_loaded = True
				try:
					if sample_doc is None:
						# no document to render against — check the template alone
						get_jenv().parse(markup)
						continue
					markup = render_typst_template(markup, {"doc": sample_doc})
				except Exception as e:
					frappe.throw(
						_("The Typst block in {0} has a template error: {1}").format(where, str(e)[:300]),
						title=_("Invalid Typst markup"),
					)
			try:
				compile_typst_source(markup)
			except Exception as e:
				frappe.throw(
					_("The Typst block in {0} does not compile: {1}").format(where, str(e)[:300]),
					title=_("Invalid Typst markup"),
				)

	def _typst_sample_doc(self):
		if not self.doc_type:
			return None
		if frappe.get_meta(self.doc_type).issingle:
			return frappe.get_doc(self.doc_type)
		name = frappe.db.get_value(self.doc_type, {}, "name", order_by="modified desc")
		return frappe.get_doc(self.doc_type, name) if name else None

	def validate_conditions(self):
		"""Reject a layout whose visibility conditions cannot compile.

		A condition that fails at render time is treated as "show", so a typo is
		invisible unless it is caught here."""
		try:
			layout = frappe.parse_json(self.format_data) if self.format_data else None
		except Exception:
			return
		if not isinstance(layout, dict):
			return

		for where, condition in _iter_conditions(layout):
			try:
				compile(condition, "<condition>", "eval")
			except SyntaxError as e:
				frappe.throw(
					_("{0} is not a valid condition: {1}").format(frappe.bold(where), e.msg),
					title=_("Invalid Condition"),
				)

	def validate_colors(self):
		for fieldname in ("label_color", "value_color"):
			value = self.get(fieldname)
			if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
				frappe.throw(
					_("{0} must be a hex color code like #1a5fb4").format(
						frappe.bold(_(self.meta.get_label(fieldname), context=self.doctype))
					)
				)

	def on_update(self):
		if hasattr(self, "old_doc_type") and self.old_doc_type:
			frappe.clear_cache(doctype=self.old_doc_type)
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)

		self.export_doc()
		self.clear_default_print_format_if_disabled()

	def clear_default_print_format_if_disabled(self):
		"""If this format is disabled while set as its DocType's default, unset it as default."""
		if not (self.disabled and self.doc_type):
			return

		meta = frappe.get_meta(self.doc_type)
		if meta.default_print_format != self.name:
			return

		if meta.custom:
			frappe.db.set_value("DocType", self.doc_type, "default_print_format", "")
		else:
			delete_property_setter(self.doc_type, "default_print_format")

		frappe.clear_cache(doctype=self.doc_type)
		frappe.msgprint(
			_(
				"{0} was the default print format for {1}. Since it is now disabled, it has been removed as the default."
			).format(frappe.bold(self.name), frappe.bold(self.doc_type)),
			indicator="orange",
			alert=True,
		)

	def after_rename(self, old: str, new: str, *args, **kwargs):
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)

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


def _iter_conditions(layout):
	"""Yield (label, expression) for every condition in a beta layout."""
	zones = [layout.get("header"), layout.get("footer"), *(layout.get("sections") or [])]
	for zone in zones:
		if not isinstance(zone, dict):
			continue
		yield from _condition(zone, zone.get("label") or _("Section"), "visible_if")
		columns = zone.get("columns")
		for column in columns if isinstance(columns, list) else []:
			fields = (column or {}).get("fields") if isinstance(column, dict) else None
			for df in fields if isinstance(fields, list) else []:
				if not isinstance(df, dict):
					continue
				label = df.get("label") or df.get("fieldname") or _("Field")
				yield from _condition(df, label, "visible_if")
				yield from _condition(df, label, "row_condition")
				table_columns = df.get("table_columns")
				for col in table_columns if isinstance(table_columns, list) else []:
					if isinstance(col, dict):
						yield from _condition(col, col.get("label") or label, "column_condition")


def _condition(holder, label, key):
	"""Yield (label, expression) only when the value is actually an expression."""
	condition = holder.get(key)
	if isinstance(condition, str) and condition.strip():
		yield label, condition


@frappe.whitelist()
def create_custom_format(doctype: str, name: str | int, based_on: str = "Standard"):
	doc = frappe.new_doc("Print Format")
	doc.doc_type = doctype
	doc.name = name
	doc.print_format_builder_beta = 1
	if based_on and based_on != "Standard":
		source = frappe.get_doc("Print Format", based_on)
		source.check_permission("read")
		doc.format_data = source.format_data
	else:
		# seed the layout so the format prints something before its first Save & Apply
		from frappe.printing.doctype.print_format.classic_converter import create_default_layout

		doc.format_data = frappe.as_json(create_default_layout(frappe.get_meta(doctype)))
	doc.insert()
	return doc


def _draft_payload(data: str | dict | None) -> dict:
	"""Keep only the fields the builder is allowed to hold in a draft."""
	data = frappe.parse_json(data) if data else {}
	if not isinstance(data, dict):
		frappe.throw(_("Draft data must be an object"))
	return {key: value for key, value in data.items() if key in BUILDER_DRAFT_FIELDS}


def _writable_format(name: str, modified: str | datetime):
	"""The format, refusing the write if the caller's copy is behind the database.

	`db_set` skips the timestamp check `save()` would run, so a second editor — or
	an autosave still in flight when Save & Apply lands — would otherwise overwrite
	a newer draft, or bring a discarded one back. `modified` is required for the
	same reason `client.save` sends one: a caller without it cannot be checked.
	"""
	doc = frappe.get_doc("Print Format", name)
	doc.check_permission("write")
	# lock the row for the rest of the transaction, so the check and the write that
	# follows it can't interleave with another request doing the same
	current = frappe.db.get_value("Print Format", name, "modified", for_update=True)
	if frappe.utils.cstr(current) != frappe.utils.cstr(modified):
		frappe.throw(
			_("{0} has changed since you opened it. Refresh to get the latest version.").format(
				frappe.bold(name)
			),
			frappe.TimestampMismatchError,
		)
	return doc


@frappe.whitelist()
def save_draft(name: str, data: str | dict, modified: str | datetime):
	"""Store the builder's in-progress changes without touching what prints."""
	doc = _writable_format(name, modified)
	doc.db_set("draft_data", frappe.as_json(_draft_payload(data)))
	return doc.modified


@frappe.whitelist()
def apply_draft(name: str, modified: str | datetime, data: str | dict | None = None):
	"""Copy the draft onto the fields that print, then clear it."""
	doc = _writable_format(name, modified)
	for field, value in _draft_payload(data if data is not None else doc.draft_data).items():
		doc.set(field, value)
	doc.draft_data = None
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def discard_draft(name: str, modified: str | datetime):
	"""Throw away the draft; what prints is untouched either way."""
	doc = _writable_format(name, modified)
	doc.db_set("draft_data", None)
	return doc.modified


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
