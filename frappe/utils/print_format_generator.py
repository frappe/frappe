# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

import copy
from typing import ClassVar

import frappe
from frappe import _
from frappe.utils.data import cint
from frappe.utils.jinja_globals import is_rtl


@frappe.whitelist()
def render_jinja_template(template: str, doctype: str, docname: str) -> str:
	"""Render a raw Jinja2 template string with doc context (used by the print format builder preview)."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("print")
	# template is rendered inside frappe's SandboxedEnvironment (Jinja2 sandbox).
	# The caller must hold the "print" permission on the document before reaching this line.
	try:
		return frappe.render_template(
			template, {"doc": doc}
		)  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	except Exception as e:
		# fail with 417 instead of 500 so the canvas can degrade inline
		# rather than the client popping the error-report dialog
		frappe.clear_last_message()
		frappe.throw(_("Failed to render template: {0}").format(str(e)), frappe.ValidationError)


@frappe.whitelist()
def download_pdf(
	doctype: str,
	name: str | int,
	print_format: str | None = None,
	letterhead: str | None = None,
	settings: str | dict | None = None,
):
	from frappe.www.printview import resolve_print_format, set_link_titles, validate_print

	doc = frappe.get_doc(doctype, name)
	validate_print(doc)
	set_link_titles(doc)
	print_format, is_beta = resolve_print_format(print_format, doc.meta)
	if not is_beta:
		# jinja formats have no layout for the generator — hand off to the
		# legacy pipeline, which reads the format's template
		from frappe.utils.print_format import download_pdf as download_jinja_pdf

		return download_jinja_pdf(doctype, name, format=print_format.name, letterhead=letterhead)
	generator = PrintFormatGenerator(print_format, doc, letterhead, settings=frappe.parse_json(settings))
	pdf = generator.render_pdf()

	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"


def get_typst_pdf(print_format, html, options, output, pdf_generator=None):
	"""`pdf_generator` hook: claims builder formats whose renderer is Typst."""
	if pdf_generator != "Typst":
		return
	generator = getattr(frappe.local, "print_format_generator", None)
	if generator is None:
		from frappe.model.document import Document

		fd = frappe.form_dict
		if not print_format or not fd.get("doctype") or not fd.get("name"):
			return
		pf = frappe.get_doc("Print Format", print_format)
		if not pf.get("print_format_builder_beta"):
			return
		doc = fd.get("doc")
		if not isinstance(doc, Document):
			doc = frappe.get_doc(fd.doctype, fd.name)
		generator = PrintFormatGenerator(pf, doc, fd.get("letterhead"), no_letterhead=fd.get("no_letterhead"))
	return generator.render_typst_pdf(password=(options or {}).get("password"))


def is_qr_barcode_options(options: str | None) -> bool:
	"""Whether a Barcode docfield's options ask for a QR code — either the bare
	string "qrcode"/"qr" or JsBarcode-style JSON like {"format": "qrcode"}."""
	import json

	options = (options or "").strip()
	if options.lower() in ("qr", "qrcode"):
		return True
	try:
		return json.loads(options).get("format", "").lower() in ("qr", "qrcode")
	except Exception:
		return False


@frappe.whitelist()
def get_qr_code(value: str) -> str:
	"""Return a QR code for `value` as an SVG data URI (used by Barcode print elements)."""
	import base64
	import io

	from pyqrcode import create as qrcreate

	stream = io.BytesIO()
	qrcreate(value).svg(stream, scale=5, quiet_zone=1)
	return "data:image/svg+xml;base64," + base64.b64encode(stream.getvalue()).decode()


@frappe.whitelist()
def get_formatted_field_values(doctype: str, name: str) -> dict:
	"""Return the same formatted value each field prints (`doc.get_formatted`) so the
	builder canvas shows the server's output instead of re-formatting client-side.

	`values` holds parent fields; `child` maps each table field to a per-row list
	of its cells' formatted values (row order matches the document)."""
	from frappe.model import table_fields
	from frappe.www.printview import set_link_titles

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	set_link_titles(doc)

	def has_access(d, df):
		return not (df.permlevel or 0) or d.has_permlevel_access_to(df.fieldname, df)

	def formatted_fields(d):
		out = {}
		for df in d.meta.fields:
			if df.fieldtype in table_fields or not has_access(d, df):
				continue
			try:
				out[df.fieldname] = d.get_formatted(df.fieldname)
			except Exception:
				continue
		return out

	values = {}
	child = {}
	for df in doc.meta.fields:
		if df.fieldtype in table_fields:
			child[df.fieldname] = [formatted_fields(row) for row in doc.get(df.fieldname) or []]
			if df.fieldtype == "Table MultiSelect" and has_access(doc, df):
				try:
					values[df.fieldname] = doc.get_formatted(df.fieldname)
				except Exception:
					pass
		elif has_access(doc, df):
			try:
				values[df.fieldname] = doc.get_formatted(df.fieldname)
			except Exception:
				continue
	return {"values": values, "child": child}


def _builder_preview_generator(
	print_format: str | dict,
	doctype: str,
	name: str | None = None,
	letterhead: str | None = None,
	settings: str | dict | None = None,
) -> "PrintFormatGenerator | None":
	"""Permission gate and generator for the builder's unsaved-format previews.

	Shared by the HTML and PDF entry points so the checks below have one home.
	Returns None when the document type has nothing printable to sample.
	"""
	from frappe.printing.doctype.print_format.print_format import printable_sample
	from frappe.www.printview import validate_print

	frappe.has_permission("Print Format", "write", throw=True)

	pf = frappe.get_doc(frappe.parse_json(print_format))
	if pf.doctype != "Print Format":
		frappe.throw(_("Expected an unsaved Print Format document"))

	name = name or printable_sample(doctype)
	if not name:
		return None

	doc = frappe.get_doc(doctype, name)
	validate_print(doc)

	return PrintFormatGenerator(pf, doc, letterhead, settings=frappe.parse_json(settings))


@frappe.whitelist()
def render_builder_preview(
	print_format: str | dict,
	doctype: str,
	name: str | None = None,
	letterhead: str | None = None,
	settings: str | dict | None = None,
) -> str:
	"""Render print HTML for an UNSAVED builder format.

	The print format builder holds the format in memory; this lets its preview
	reflect edits before they are saved, using the same renderer the PDF uses so
	the preview cannot drift from the printed output. ``print_format`` is the
	in-memory Print Format document (dict/JSON), not a saved name.
	"""
	generator = _builder_preview_generator(print_format, doctype, name, letterhead, settings)
	return generator.get_html_preview() if generator else ""


@frappe.whitelist()
def download_builder_preview_pdf(
	print_format: str | dict,
	doctype: str,
	name: str | None = None,
	letterhead: str | None = None,
	settings: str | dict | None = None,
):
	"""Render a PDF for an UNSAVED builder format.

	Same contract as :func:`render_builder_preview`, but through the PDF renderer.
	Paginating HTML in the browser can only ever approximate where Chromium breaks
	a page, so the builder's paged preview asks Chromium instead of guessing.
	"""
	generator = _builder_preview_generator(print_format, doctype, name, letterhead, settings)
	if not generator:
		frappe.throw(_("No document available to preview"))

	frappe.local.response.filename = "preview.pdf"
	frappe.local.response.filecontent = generator.render_pdf()
	frappe.local.response.type = "pdf"


def get_html(
	doctype,
	name,
	print_format,
	letterhead=None,
	action_banner=None,
	style=None,
	trigger_print=False,
	settings=None,
	no_letterhead=None,
):
	from frappe.www.printview import validate_print

	doc = frappe.get_doc(doctype, name)
	validate_print(doc)
	generator = PrintFormatGenerator(
		print_format, doc, letterhead, style=style, settings=settings, no_letterhead=no_letterhead
	)
	return generator.get_html_preview(action_banner=action_banner, trigger_print=trigger_print)


class PrintFormatGenerator:
	"""Generate a PDF of a Document using Chromium-based rendering."""

	_TOP_POSITIONS: ClassVar[set[str]] = {"top_left", "top_center", "top_right"}
	_BOTTOM_POSITIONS: ClassVar[set[str]] = {"bottom_left", "bottom_center", "bottom_right"}
	_ALIGN_MAP: ClassVar[dict[str, str]] = {
		"top_left": "left",
		"top_center": "center",
		"top_right": "right",
		"bottom_left": "left",
		"bottom_center": "center",
		"bottom_right": "right",
	}
	_FIELD_RENDERERS: ClassVar[dict[str, str]] = {"HTML Editor": "HTML", "Markdown Editor": "Markdown"}
	JUSTIFY_MODES: ClassVar[frozenset[str]] = frozenset(
		{"space-between", "space-evenly", "center", "right-end"}
	)

	def __init__(self, print_format, doc, letterhead=None, style=None, settings=None, no_letterhead=None):
		self.print_format = (
			print_format
			if not isinstance(print_format, str)
			else frappe.get_doc("Print Format", print_format)
		)
		self.doc = doc
		self.style = style
		self.settings_override = settings or {}
		self._header_absorbs_top_margin = False
		self._logged_conditions = set()
		self.letterhead = None

		self.build_context()
		self.layout = self.get_layout(self.print_format)
		self.context.layout = self.layout
		self.letterhead = self.get_letterhead(letterhead, no_letterhead)
		self.context.letterhead = self.letterhead

	def get_letterhead(self, letterhead, no_letterhead):
		"""Resolve the letter head to print, most specific choice first.

		Mirrors ``printview.get_letter_head`` so a builder format prints the same
		letter head a template one would, and adds the format's own choice: a layout
		that names a letter head outranks the document's field. ``no_letterhead``
		left unset falls back to the Print Settings toggle, as templates do.
		"""
		if no_letterhead is None:
			no_letterhead = not cint(self.print_settings.with_letterhead)
		if cint(no_letterhead) or letterhead == _("No Letterhead"):
			return None

		name = letterhead
		if not name:
			layout = self.layout or {}
			if "letter_head" in layout:
				# an empty value is an explicit removal, not an unset field
				name = layout.get("letter_head")
				if not name:
					return None
			else:
				name = self.doc.get("letter_head") or frappe.db.get_value(
					"Letter Head", {"is_default": 1}, "name"
				)
		# a stale link shouldn't fail the render — templates degrade to no letter head too
		if not name or not frappe.db.exists("Letter Head", name):
			return None
		return frappe.get_doc("Letter Head", name)

	def build_context(self):
		self.print_settings = frappe.get_doc("Print Settings")
		if self.settings_override:
			from frappe.www.printview import get_allowed_print_settings_override

			self.print_settings.update(get_allowed_print_settings_override(self.doc, self.settings_override))

		from frappe.www.printview import run_before_print

		run_before_print(self.doc, self.print_settings.as_dict())

		page_width_map = {"A4": 210, "Letter": 216}
		page_width = page_width_map.get(self.print_settings.pdf_page_size) or 210
		body_width = page_width - self.print_format.margin_left - self.print_format.margin_right
		style_name = self.style or self.print_settings.print_style
		print_style = (
			frappe.get_doc("Print Style", style_name)
			if style_name and frappe.db.exists("Print Style", style_name)
			else None
		)
		self.context = frappe._dict(
			{
				"doc": self.doc,
				"print_format": self.print_format,
				"print_settings": self.print_settings,
				"print_style": print_style,
				"letterhead": self.letterhead,
				"page_width": page_width,
				"body_width": body_width,
				"lang": frappe.local.lang,
				"layout_direction": "rtl" if is_rtl() else "ltr",
			}
		)

	# ----- HTML preview (browser printview) ------------------------------

	def get_html_preview(self, action_banner=None, trigger_print=False):
		repeat = self.print_settings.repeat_header_footer
		frame_header = self._render_overlay("header", with_page_no=False) if repeat else None
		frame_footer = self._render_overlay("footer", with_page_no=False) if repeat else None
		if repeat and (frame_header or frame_footer):
			self.context.repeat_frame = True
			self.context.frame_header = frame_header or ""
			self.context.frame_footer = frame_footer or ""
			self.context.header = ""
			self.context.footer = ""
		else:
			self.context.repeat_frame = False
			header_html, footer_html = self.get_header_footer_html()
			self.context.header = header_html
			self.context.footer = footer_html
		self.context.action_banner = action_banner
		if trigger_print:
			from frappe.www.printview import trigger_print_script

			self.context.trigger_print_script = trigger_print_script
		return self.get_main_html()

	def get_main_html(self):
		self.context.css = frappe.render_template("templates/print_format/print_format.css", self.context)
		return frappe.render_template("templates/print_format/print_format.html", self.context)

	def get_header_footer_html(self):
		header_html = footer_html = None
		if self.letterhead:
			header_html = frappe.render_template("templates/print_format/print_header.html", self.context)
			footer_html = frappe.render_template("templates/print_format/print_footer.html", self.context)
		return header_html, footer_html

	# ----- PDF (Chrome) --------------------------------------------------

	def render_pdf(self, password=None):
		"""Return PDF bytes using the format's renderer.

		Renderers other than the built-in Chromium are resolved through the
		`pdf_generator` hook, so an app can register its own the same way the
		Typst renderer is."""
		from frappe.utils.pdf import get_chrome_pdf

		pf = self.print_format
		generator_name = pf.get("pdf_generator") or "chrome"
		# chrome renders below; wkhtmltopdf never reached hooks before this branch either
		if generator_name not in ("chrome", "wkhtmltopdf"):
			previous = getattr(frappe.local, "print_format_generator", None)
			frappe.local.print_format_generator = self
			try:
				for hook in frappe.get_hooks("pdf_generator"):
					# hook targets come from installed apps' hooks.py, never from request data
					# nosemgrep: frappe-semgrep-rules.rules.security.frappe-codeinjection-eval
					pdf = frappe.call(
						hook,
						print_format=pf.name,
						html=None,
						options={"password": password} if password else {},
						output=None,
						pdf_generator=generator_name,
					)
					if pdf:
						return pdf
			finally:
				frappe.local.print_format_generator = previous
		from frappe.utils.typst_emitter import has_typst_blocks

		if has_typst_blocks(self.layout):
			frappe.throw(
				_(
					"This format uses a Typst block, which only the Typst renderer can print. Set the PDF Renderer to Typst or remove the block."
				),
				title=_("Chromium renderer unavailable"),
			)
		html = self._build_html_for_chrome()
		options = {
			"margin-top": f"{pf.margin_top}mm",
			"margin-bottom": f"{pf.margin_bottom}mm",
			"margin-left": f"{pf.margin_left}mm",
			"margin-right": f"{pf.margin_right}mm",
		}
		if self._header_absorbs_top_margin:
			options["header-includes-top-margin"] = True
		if password:
			options["password"] = password
		return get_chrome_pdf(
			print_format=pf.name,
			html=html,
			options=options,
			output=None,
			pdf_generator="chrome",
		)

	def render_typst_pdf(self, password=None):
		"""Compile the resolved layout through Typst — ~10-15x faster than Chromium.

		Refuses (rather than silently falling back) when the format uses features
		Typst cannot express, so the renderer a user chose is the one that runs."""
		import os
		import tempfile

		import typst

		from frappe.utils.typst_emitter import (
			TypstEmitter,
			ensure_typst_fonts,
			letterhead_blockers,
			typst_blockers,
			typst_font_paths,
		)

		blockers = typst_blockers(self.print_format, self.layout)
		if self.letterhead:
			# the letter head actually printing may differ from the layout's
			blockers = list(dict.fromkeys(blockers + letterhead_blockers(self.letterhead.as_dict())))
		if blockers:
			frappe.throw(
				_("This format can no longer render through Typst: {0}").format(", ".join(blockers)),
				title=_("Typst renderer unavailable"),
			)
		if password:
			frappe.throw(_("PDF encryption is not supported by the Typst renderer"))

		ensure_typst_fonts(self.print_format.get("font"))
		emitter = TypstEmitter(self)
		emitter.prepare()
		repeat = cint(self.print_settings.get("repeat_header_footer"))

		with tempfile.TemporaryDirectory() as tmp:

			def write(name, content, mode="w"):
				# names are emitter-generated constants inside a fresh tempdir
				path = os.path.join(tmp, name)
				# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
				with open(path, mode) as f:
					f.write(content)
				return path

			import json

			written = set()

			def write_assets(assets):
				for name, data in assets.items():
					if name not in written:
						written.add(name)
						write(name, data, "wb")

			heights = {"pfhdr": 0.0, "pfftr": 0.0}
			if repeat and (emitter.header_src or emitter.footer_src):
				write_assets(emitter.assets)
				measure_path = write("measure.typ", emitter.measure_source())
				for label in list(heights):
					found = json.loads(
						typst.query(measure_path, f"<{label}>", root=tmp, font_paths=typst_font_paths())
					)
					if found:
						heights[label] = float(found[0].get("value") or 0)

			source, assets = emitter.emit(
				repeat_header_footer=repeat,
				header_height_pt=heights["pfhdr"],
				footer_height_pt=heights["pfftr"],
			)
			path = write("main.typ", source)
			write_assets(assets)
			# root pins file access to the tempdir — matters once formats can
			# carry raw Typst markup (Typst blocks)
			return typst.compile(path, root=tmp, font_paths=typst_font_paths())

	def _build_html_for_chrome(self):
		"""Build the body HTML for the Chrome PDF pipeline.

		When ``repeat_header_footer`` is enabled (default), letterhead and
		layout header/footer are placed in ``#header-html`` / ``#footer-html``
		overlay divs so they repeat on every PDF page.

		When ``repeat_header_footer`` is disabled:
		  - Letterhead + layout header/footer → rendered inline in the body
		    (appear on page 1 / last page only via ``chrome_layout_header/footer``).
		  - Page numbers → still placed in a minimal ``#header-html`` / ``#footer-html``
		    overlay so they continue to repeat on every page if the user enabled them.
		"""
		self.context.for_chrome = True
		self._header_absorbs_top_margin = False
		self.context.repeat_frame = False
		self.context.header_height = 0
		self.context.footer_height = 0

		repeat = self.print_settings.repeat_header_footer

		if repeat:
			header = self._render_overlay("header")
			footer = self._render_overlay("footer")
			self.context.header = f'<div id="header-html">{header}</div>' if header else ""
			self.context.footer = f'<div id="footer-html">{footer}</div>' if footer else ""
			self.context.chrome_layout_header = ""
			self.context.chrome_layout_footer = ""
		else:
			# Letterhead + layout content → inline (once only, no repeat).
			self.context.chrome_layout_header = self._render_overlay("header", with_page_no=False) or ""
			self.context.chrome_layout_footer = self._render_overlay("footer", with_page_no=False) or ""
			# Page numbers → minimal overlay so they still repeat on every page.
			page_no_header = self._render_page_no_overlay("header")
			page_no_footer = self._render_page_no_overlay("footer")
			self.context.header = f'<div id="header-html">{page_no_header}</div>' if page_no_header else ""
			self.context.footer = f'<div id="footer-html">{page_no_footer}</div>' if page_no_footer else ""

		return self.get_main_html()

	def _reserve_top_margin(self, html: str) -> str:
		"""Reserve the page's top margin *below* the page number.

		browser.py then drops the header page's own ``marginTop`` (via the
		``header-includes-top-margin`` option), so the number sits flush to the
		paper edge while everything after it keeps the configured margin.
		"""
		top_margin = float(self.print_format.margin_top or 0)
		if not top_margin:
			return html
		self._header_absorbs_top_margin = True
		return f'<div style="padding-top:{top_margin}mm">{html}</div>'

	def _render_page_no_overlay(self, kind: str) -> str | None:
		"""Return only the page-number HTML for kind ('header'/'footer'), or None."""
		is_header = kind == "header"
		page_pos = (self.print_format.page_number or "").lower().replace(" ", "_")
		valid_positions = self._TOP_POSITIONS if is_header else self._BOTTOM_POSITIONS
		if page_pos not in valid_positions:
			return None
		page_no_html = self._page_number_html(page_pos)
		if not is_header:
			return page_no_html
		return page_no_html + self._reserve_top_margin("")

	def _render_overlay(self, kind: str, with_page_no: bool = True) -> str | None:
		"""Render letterhead, layout.header/footer, and page number for the Chrome overlay.

		All three are included so they repeat on every PDF page.  Height measurement
		is reliable because ``chrome_pdf_header_footer.html`` applies ``overflow: hidden``
		to ``.wrapper``, creating a BFC that contains floated letterhead children.
		"""
		is_header = kind == "header"
		page_pos = (self.print_format.page_number or "").lower().replace(" ", "_")
		valid_positions = self._TOP_POSITIONS if is_header else self._BOTTOM_POSITIONS
		wants_page_no = with_page_no and page_pos in valid_positions

		if is_header:
			letterhead_html = self.letterhead and self.letterhead.content
			layout_template = self.layout.get("header") if self.layout else None
		else:
			letterhead_html = self.letterhead and self.letterhead.footer
			layout_template = self.layout.get("footer") if self.layout else None

		if not (letterhead_html or wants_page_no or layout_template):
			return None

		page_no_html = self._page_number_html(page_pos) if wants_page_no else None
		ctx = {"doc": self.context.doc}

		parts = []
		body_parts = []
		if is_header and page_no_html:
			parts.append(page_no_html)
		if letterhead_html:
			body_parts.append(
				'<div class="letter-head">' + frappe.render_template(letterhead_html, ctx) + "</div>"
			)
		if layout_template:
			if isinstance(layout_template, str):
				# layout_template is persisted header/footer HTML from the stored Print Format document.
				zone_html = frappe.render_template(
					layout_template, ctx
				)  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
			else:
				# Section object — render using the same logic as print_format.html
				zone_html = self._render_zone_section(layout_template, ctx["doc"])
			if zone_html:
				body_parts.append('<div class="document-header-content">' + zone_html + "</div>")
		if not is_header and page_no_html:
			body_parts.append(page_no_html)

		if is_header and page_no_html:
			body_parts = [self._reserve_top_margin("\n".join(body_parts))]
		parts.extend(body_parts)
		return "\n".join(parts) or None

	_ZONE_SECTION_TEMPLATE = """\
{%- set justify_classes = {'space-between': 'row-col-space-between', 'space-evenly': 'row-col-space-evenly', 'center': 'row-col-center', 'right-end': 'row-col-right-end'} -%}
{%- set ns = namespace(has_fields=false) -%}
{%- for col in section.columns -%}{%- for df in col.get('fields', []) -%}{%- set ns.has_fields = true -%}{%- endfor -%}{%- endfor -%}
{%- if ns.has_fields -%}
{%- set col_gap = (section.gap if section.gap is defined and section.gap is not none else 20)|string + 'px' -%}
<div class="section section-columns row {{ justify_classes.get(section.get('justify'), '') }}" style="gap:{{ col_gap }}">
{%- for column in section.columns %}
<div class="column col"{% if column.get('width') %} style="flex: {{ column.get('width')|float }} 1 0%"{% endif %}>
{%- for df in column.get('fields', []) -%}
{%- if not df.get('_hidden') -%}
{%- if df.fieldtype == 'HTML' and df.html -%}
<div class="custom-html">{{ frappe.render_template(df.html, {'doc': doc}) }}</div>
{%- elif df.fieldtype == 'Spacer' -%}
<div style="height:{{ (df.height|int|string + 'px') if df.get('height') else '1em' }}"></div>
{%- elif df.fieldtype == 'Divider' -%}
<hr style="border-top:1px solid #e5e7eb;margin:4px 0"/>
{%- elif df.fieldtype == 'Image' -%}
{%- set _src = df.image_url or doc.get(df.fieldname) -%}
{%- if _src -%}
<div{% if df.align and df.align != 'left' %} style="text-align:{{ df.align }}"{% endif %}>
<img src="{{ _src }}" style="max-width:100%;{% if df.width %}width:{{ df.width|e }};{% endif %}">
</div>
{%- endif -%}
{%- elif df.fieldtype == 'Barcode' -%}
{%- if df.get('_qr_data_uri') -%}
<div{% if df.align and df.align != 'left' %} style="text-align:{{ df.align }}"{% endif %}>
<img src="{{ df._qr_data_uri }}" style="{% if df.width %}width:{{ df.width|e }};{% else %}width:35mm;{% endif %}">
</div>
{%- endif -%}
{%- else -%}
{%- set _raw = doc.get(df.fieldname) -%}
{%- if _raw is not none and _raw != '' -%}
<div class="field-render">
{%- if df.show_label != 'hide' %}<div class="label">{{ _(df.label or df.fieldname) }}</div>{%- endif -%}
<div class="value">{{ doc.get_formatted(df.fieldname) }}</div>
</div>
{%- endif -%}
{%- endif -%}
{%- endif -%}
{%- endfor -%}
</div>
{%- endfor %}
</div>
{%- endif -%}
"""

	def _render_zone_section(self, section: dict, doc) -> str:
		"""Render a header/footer zone section dict to HTML for the Chrome overlay."""
		# _ZONE_SECTION_TEMPLATE is a hardcoded class-level string constant, not user input.
		return frappe.render_template(
			self._ZONE_SECTION_TEMPLATE, {"section": section, "doc": doc}
		)  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti

	def _page_number_html(self, position: str) -> str:
		align = self._ALIGN_MAP.get(position, "center")
		return (
			f'<div style="text-align:{align};font-size:10px;padding:2px 0;">'
			'<span class="page"></span>'
			f" {_('of')} "
			'<span class="topage"></span>'
			"</div>"
		)

	EMPTY_LAYOUT: ClassVar[dict] = {
		"sections": [],
		"header": {"columns": []},
		"footer": {"columns": []},
	}

	def get_layout(self, print_format):
		try:
			layout = frappe.parse_json(print_format.format_data) or copy.deepcopy(self.EMPTY_LAYOUT)
		except Exception:
			frappe.log_error(title=f"Unreadable print format layout: {print_format.name}")
			layout = copy.deepcopy(self.EMPTY_LAYOUT)
		if isinstance(layout, list) and layout:
			from frappe.printing.doctype.print_format.classic_converter import convert_classic_to_beta

			layout, _dropped = convert_classic_to_beta(
				layout, frappe.get_meta(print_format.doc_type), print_format
			)
			if not print_format.page_number or print_format.page_number == "Hide":
				print_format.page_number = "Bottom Center"
		layout = self.normalise_layout(layout)
		layout = self.apply_permlevel_access(layout)
		layout = self.set_field_renderers(layout)
		layout = self.prune_table_columns(layout)
		layout = self.process_margin_texts(layout)
		return layout

	def normalise_layout(self, layout):
		"""Drop anything the builder could not have produced, rather than crashing."""
		if not isinstance(layout, dict):
			return copy.deepcopy(self.EMPTY_LAYOUT)

		def clean_zone(zone):
			if not isinstance(zone, dict):
				return {"columns": []}
			columns = [
				{**col, "fields": [clean_field(f) for f in col.get("fields") or [] if isinstance(f, dict)]}
				for col in zone.get("columns") or []
				if isinstance(col, dict)
			]
			cleaned = {**zone, "columns": columns}
			# justify names a CSS class, so only the modes we ship may reach the markup
			if cleaned.get("justify") not in self.JUSTIFY_MODES:
				cleaned.pop("justify", None)
			return cleaned

		def clean_field(df):
			if "table_columns" not in df:
				return df
			table_columns = df["table_columns"]
			if not isinstance(table_columns, list):
				table_columns = []
			return {**df, "table_columns": [c for c in table_columns if isinstance(c, dict)]}

		sections = layout.get("sections")
		layout["sections"] = (
			[clean_zone(s) for s in sections if isinstance(s, dict)] if isinstance(sections, list) else []
		)
		for zone in ("header", "footer"):
			layout[zone] = clean_zone(layout.get(zone))
		return layout

	def layout_columns(self, layout):
		for section in layout.get("sections", []):
			yield from section.get("columns", [])
		for zone in ("header", "footer"):
			zone_layout = layout.get(zone)
			if isinstance(zone_layout, dict):
				yield from zone_layout.get("columns", [])

	@staticmethod
	def has_field_access(doc, meta, fieldname) -> bool:
		if not fieldname:
			return True
		df = meta.get_field(fieldname)
		if not df or not (df.permlevel or 0):
			return True
		return doc.has_permlevel_access_to(fieldname, df)

	def apply_permlevel_access(self, layout):
		"""Drop fields the user has no permlevel read access to.

		The layout is authored against the doctype, not the reader, so a format may
		reference permlevel-restricted fields that this user must not see."""
		meta = self.doc.meta
		for column in self.layout_columns(layout):
			fields = [
				df
				for df in column.get("fields", [])
				if self.has_field_access(self.doc, meta, df.get("fieldname"))
			]
			column["fields"] = fields
			for df in fields:
				if df.get("fieldtype") == "Repeater":
					rows = self.doc.get(df.get("source")) or []
					if not rows:
						continue
					child, child_meta = rows[0], rows[0].meta
					for col in df.get("repeater_columns") or []:
						col["template"] = [
							tok
							for tok in col.get("template") or []
							if not (
								isinstance(tok, dict)
								and tok.get("t") == "f"
								and not self.has_field_access(child, child_meta, tok.get("v"))
							)
						]
					continue
				if df.get("fieldtype") != "Table" or not df.get("table_columns"):
					continue
				rows = self.doc.get(df.get("fieldname")) or []
				if not rows:
					continue
				child, child_meta = rows[0], rows[0].meta
				df["table_columns"] = [
					col
					for col in df["table_columns"]
					if self.has_field_access(child, child_meta, col.get("fieldname"))
				]
				for col in df["table_columns"]:
					if col.get("merged_fields"):
						col["merged_fields"] = [
							mf
							for mf in col["merged_fields"]
							if self.has_field_access(child, child_meta, mf.get("fieldname"))
						]
		return layout

	def prune_table_columns(self, layout):
		"""Drop table columns that fail their column_condition (doc-scoped) or that are
		empty across all rows, then renormalize widths. A bad condition fails open."""
		from frappe.www.printview import column_has_value

		eval_locals = {"doc": self.doc, "print_settings": self.print_settings}
		for column in self.layout_columns(layout):
			for df in column.get("fields", []):
				if df.get("fieldtype") != "Table" or not df.get("table_columns"):
					continue
				rows = df.get("_rows") if df.get("_rows") is not None else self.doc.get(df.get("fieldname"))
				rows = rows or []
				kept = []
				for col in df["table_columns"]:
					if not self.column_condition_met(col, eval_locals):
						continue
					if (
						rows
						and col.get("fieldname") != "idx"
						and not column_has_value(rows, col.get("fieldname"), frappe._dict(col))
					):
						continue
					kept.append(col)
				total = sum(col.get("width") or 0 for col in kept)
				if total:
					for col in kept:
						if col.get("width"):
							col["width"] = round(col["width"] / total * 100, 2)
				df["table_columns"] = kept
		return layout

	def eval_condition(self, condition, eval_locals, where):
		"""Evaluate a visibility condition. A broken expression keeps the thing
		visible, logged once per expression so a row condition cannot write one log
		row per child row."""
		if not isinstance(condition, str):
			return True
		try:
			return bool(frappe.safe_eval(condition, None, eval_locals))
		except Exception:
			if condition not in self._logged_conditions:
				self._logged_conditions.add(condition)
				frappe.log_error(
					title=f"Print format condition failed: {self.print_format.name}",
					message=f"{where}: {condition}",
				)
			return True

	def column_condition_met(self, col, eval_locals):
		condition = col.get("column_condition")
		if not condition:
			return True
		return self.eval_condition(
			condition, eval_locals, f"column {col.get('label') or col.get('fieldname')}"
		)

	def _prepare_field(self, df, section, eval_locals):
		if df.get("visible_if"):
			df["_hidden"] = not self.eval_condition(
				df["visible_if"], eval_locals, f"field {df.get('label') or df.get('fieldname')}"
			)
		fieldtype = df.get("fieldtype", "Data")
		df["renderer"] = self._FIELD_RENDERERS.get(fieldtype) or fieldtype.replace(" ", "")
		df["section"] = section
		self.prepare_barcode(df)
		self.prepare_linked_field(df)
		self.prepare_summary_table(df)
		self.filter_conditional_rows(df)

	def set_field_renderers(self, layout):
		eval_locals = {"doc": self.doc, "print_settings": self.print_settings}
		for section in layout["sections"]:
			if section.get("visible_if"):
				section["_hidden"] = not self.eval_condition(
					section["visible_if"], eval_locals, f"section {section.get('label') or ''}"
				)
			for column in section["columns"]:
				for df in column["fields"]:
					self._prepare_field(df, section, eval_locals)

		# Also process header/footer zones if they are section objects
		for zone_key in ("header", "footer"):
			zone = layout.get(zone_key)
			if isinstance(zone, dict) and "columns" in zone:
				for column in zone.get("columns", []):
					for df in column.get("fields", []):
						self._prepare_field(df, zone, eval_locals)

		return layout

	def filter_conditional_rows(self, df):
		"""Drop repeater/table rows whose row_condition is falsy; a bad expression fails
		open (keeps the row) so a typo never silently blanks the table."""
		fieldtype = df.get("fieldtype")
		if fieldtype == "Repeater":
			source = df.get("source")
		elif fieldtype == "Table":
			source = df.get("fieldname")
		else:
			return
		if not df.get("row_condition") or not source:
			return
		condition = df["row_condition"]
		eval_locals = {"doc": self.doc, "print_settings": self.print_settings}
		kept = []
		for row in self.doc.get(source) or []:
			if self.eval_condition(condition, {**eval_locals, "row": row}, f"rows of {source}"):
				kept.append(row)
		df["_rows"] = kept

	def prepare_barcode(self, df):
		"""Resolve JsBarcode options / QR data URI for Barcode layout elements."""
		if df.get("fieldtype") != "Barcode":
			return
		if not df.get("custom"):
			# a dragged Barcode docfield prints whatever it stores; a docfield
			# whose options ask for a qr code prints its value as one — the
			# field decides the format, the builder offers no override
			meta_df = frappe.get_meta(self.doc.doctype).get_field(df.get("fieldname"))
			value = self.doc.get(df.get("fieldname"))
			if value and meta_df and is_qr_barcode_options(meta_df.options):
				df["barcode_format"] = "QR"
				df["_qr_data_uri"] = get_qr_code(str(value))
			return
		if df.get("barcode_format") == "QR":
			value = (
				self.doc.get(df.get("barcode_field")) if df.get("barcode_field") else df.get("barcode_value")
			)
			if value:
				df["_qr_data_uri"] = get_qr_code(str(value))
		else:
			df["_barcode_options"] = frappe.as_json(
				{
					"format": df.get("barcode_format") or "CODE128",
					"displayValue": bool(df.get("show_text", True)),
					"height": 40,
					"margin": 0,
				},
				indent=None,
			)

	def prepare_linked_field(self, df):
		"""Resolve a Linked Field's one-hop path (link_field.target_field) to a
		formatted value from the linked document."""
		if df.get("fieldtype") != "Linked Field" or not df.get("link_path"):
			return
		path = df["link_path"]
		if "." not in path:
			return
		link_fieldname, target_fieldname = path.split(".", 1)
		link_df = self.doc.meta.get_field(link_fieldname)
		if not link_df or link_df.fieldtype != "Link" or not link_df.options:
			return
		name = self.doc.get(link_fieldname)
		if not name or not frappe.has_permission(link_df.options, "read"):
			return
		target_meta = frappe.get_meta(link_df.options)
		target_df = target_meta.get_field(target_fieldname)
		if not target_df:
			return
		value = frappe.db.get_value(link_df.options, name, target_fieldname)
		if value is None:
			return
		df["_value"] = frappe.format_value(value, df=target_df, doc=self.doc)

	def prepare_summary_table(self, df):
		"""Group a child table's rows and evaluate per-group column expressions.

		Each column expr sees: key (the group value), g (a dict of summed numeric
		fields for the group), doc, and tax_rate(pattern) which returns the rate of
		the first doc.taxes row whose description contains the pattern."""
		if df.get("fieldtype") != "Summary Table" or not df.get("source") or not df.get("columns"):
			return
		rows = self.doc.get(df["source"]) or []
		if not rows:
			return
		child_meta = rows[0].meta
		numeric_fields = [
			f.fieldname for f in child_meta.fields if f.fieldtype in ("Currency", "Float", "Int")
		]

		def tax_rate(pattern):
			for tax in self.doc.get("taxes") or []:
				if pattern.lower() in (tax.description or "").lower():
					return tax.rate or 0
			return 0

		groups = {}
		for row in rows:
			key = row.get(df.get("group_by")) or ""
			g = groups.setdefault(key, frappe._dict({f: 0 for f in numeric_fields}))
			for f in numeric_fields:
				g[f] += row.get(f) or 0
		total_g = frappe._dict({f: sum(g[f] for g in groups.values()) for f in numeric_fields})

		def format_cell(value, column):
			if column.get("format") == "currency":
				return frappe.utils.fmt_money(value, currency=self.doc.get("currency"))
			return value if isinstance(value, str) else frappe.utils.cstr(value)

		def eval_row(key, g):
			cells = []
			for column in df["columns"]:
				try:
					value = frappe.safe_eval(
						column.get("expr") or "''",
						None,
						{"key": key, "g": g, "doc": self.doc, "tax_rate": tax_rate},
					)
				except Exception:
					value = ""
				align = column.get("align") or ("right" if column.get("format") == "currency" else "center")
				cells.append({"value": format_cell(value, column), "align": align})
			return cells

		body = [eval_row(key, g) for key, g in groups.items()]
		totals = None
		if df.get("show_totals"):
			totals = eval_row(_("Total"), total_g)
			for i, column in enumerate(df["columns"]):
				if not column.get("total"):
					totals[i]["value"] = _("Total") if i == 0 else ""

		head1, head2 = [], []
		i = 0
		columns = df["columns"]
		while i < len(columns):
			group = columns[i].get("group")
			if not group:
				head1.append({"label": columns[i].get("label") or "", "colspan": 1, "rowspan": 2})
				i += 1
				continue
			span = 0
			while i + span < len(columns) and columns[i + span].get("group") == group:
				head2.append({"label": columns[i + span].get("label") or ""})
				span += 1
			head1.append({"label": group, "colspan": span, "rowspan": 1})
			i += span
		if not head2:
			head1 = [{**cell, "rowspan": 1} for cell in head1]

		df["_summary"] = {"head1": head1, "head2": head2, "rows": body, "totals": totals}

	def process_margin_texts(self, layout):
		for key in (*self._TOP_POSITIONS, *self._BOTTOM_POSITIONS):
			text = layout.get("text_" + key)
			if text and "{{" in text:
				layout["text_" + key] = frappe.render_template(text, self.context)
		return layout
