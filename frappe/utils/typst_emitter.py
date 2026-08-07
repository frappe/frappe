# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Emit Typst markup from a resolved print format layout.

The emitter consumes the SAME layout `PrintFormatGenerator` renders HTML from —
after normalise_layout, permlevel stripping, visibility conditions and table
column pruning — so the two renderers can never disagree on what a user is
allowed to see. Typst receives only resolved data and geometry, never logic.

Formats that use features Typst cannot express (raw HTML blocks, Jinja field
templates, client-side barcodes, …) are refused by :func:`typst_blockers`;
they keep rendering through Chromium.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils.html_utils import unescape_html

#: px (builder/CSS space) → pt (Typst space)
PX_TO_PT = 0.75

#: field types the emitter renders; everything else with a plain value goes
#: through the Data path (label + formatted value), same as macros.html
EMITTED_FIELDTYPES = frozenset({"Divider", "Spacer", "Table"})

#: field types that disqualify a format — each with the reason shown to the user
# translated at use, not import — a module-level _() would pin the first site's language
BLOCKER_FIELDTYPES = {
	"HTML": "Custom HTML block",
	"Field Template": "Field Template (Jinja HTML)",
}

PAGE_NUMBER_POSITIONS = {
	"Top Left": ("header", "left"),
	"Top Center": ("header", "center"),
	"Top Right": ("header", "right"),
	"Bottom Left": ("footer", "left"),
	"Bottom Center": ("footer", "center"),
	"Bottom Right": ("footer", "right"),
}

RIGHT_ALIGNED_FIELDTYPES = frozenset({"Currency", "Float", "Int", "Percent"})

#: the css properties the builder writes into custom_style that we can express in
#: Typst; anything outside this list keeps the format on Chromium
TRANSLATABLE_STYLE_PROPS = frozenset(
	{
		"font-weight",
		"border-top",
		"border-bottom",
		"margin-top",
		"padding-top",
		"padding-bottom",
		"flex-direction",
		"align-items",
		"gap",
	}
)


def translate_custom_style(style: str) -> tuple[dict, list[str]]:
	"""Map a declaration list onto Typst effects; unknown properties are returned,
	never dropped — a property we cannot express keeps the format on Chromium."""
	effects, unknown = {}, []
	for declaration in (style or "").split(";"):
		if ":" not in declaration:
			continue
		prop, value = (part.strip() for part in declaration.split(":", 1))
		prop = prop.lower()
		if prop not in TRANSLATABLE_STYLE_PROPS:
			unknown.append(prop)
			continue
		if prop == "font-weight":
			if value in ("bold", "600", "700", "800", "900"):
				effects["bold"] = True
		elif prop in ("border-top", "border-bottom"):
			match = re.match(r"([\d.]+)px\s+\w+\s+(#[0-9a-fA-F]{6}|[a-z]+)", value)
			if match:
				width = round(float(match.group(1)) * PX_TO_PT, 2)
				color = match.group(2)
				paint = f'rgb("{color}")' if color.startswith("#") else color
				effects["stroke_top" if prop == "border-top" else "stroke_bottom"] = f"{width}pt + {paint}"
		elif prop in ("margin-top", "padding-top", "padding-bottom", "gap"):
			match = re.match(r"([\d.]+)(px)?$", value)
			if match:
				key = {
					"margin-top": "space_before",
					"padding-top": "inset_top",
					"padding-bottom": "inset_bottom",
					"gap": "gap",
				}[prop]
				effects[key] = round(float(match.group(1)) * PX_TO_PT, 2)
		# flex-direction / align-items describe what the structured layout
		# already does — accepted so they never block, nothing to emit
	return effects, unknown


def typst_blockers(print_format, layout) -> list[str]:
	"""Why this format cannot render through Typst — empty means it can.

	The single authority: the builder UI mirrors this to grey out the option,
	and render_pdf refuses when it is non-empty."""
	blockers = []
	if print_format.get("custom_format"):
		blockers.append(_("Custom HTML format"))
		return blockers
	if not print_format.get("print_format_builder_beta"):
		blockers.append(_("Not a builder format"))
		return blockers
	if (print_format.get("css") or "").strip():
		blockers.append(_("Custom CSS on the format"))

	if not isinstance(layout, dict):
		return blockers

	letter_head = layout.get("letter_head")
	if letter_head:
		content, custom_css = frappe.db.get_value("Letter Head", letter_head, ["content", "custom_css"]) or (
			None,
			None,
		)
		if (content or "").strip() or (custom_css or "").strip():
			blockers.append(_("Letterhead with HTML content"))

	seen = set()
	for where, node in _walk(layout):
		style = node.get("custom_style")
		if isinstance(style, str) and style.strip():
			_effects, unknown = translate_custom_style(style)
			if unknown:
				key = ("custom_style", where)
				if key not in seen:
					seen.add(key)
					blockers.append(_("Untranslatable CSS on {0}: {1}").format(where, ", ".join(unknown)))
		fieldtype_reason = BLOCKER_FIELDTYPES.get(node.get("fieldtype"))
		reason = (
			(_(fieldtype_reason) if fieldtype_reason else None)
			or _barcode_blocker(node, print_format)
			or _image_blocker(node)
		)
		if reason and reason not in seen:
			seen.add(reason)
			blockers.append(reason)
	return blockers


def _barcode_blocker(df, print_format):
	"""Only QR renders server-side; JsBarcode formats need a browser."""
	if df.get("fieldtype") != "Barcode":
		return None
	if df.get("custom"):
		return None if df.get("barcode_format") == "QR" else _("Barcode (non-QR)")
	try:
		meta_df = frappe.get_meta(print_format.doc_type).get_field(df.get("fieldname"))
	except Exception:
		meta_df = None
	from frappe.utils.print_format_generator import is_qr_barcode_options

	if meta_df and is_qr_barcode_options(meta_df.options):
		return None
	return _("Barcode (non-QR)")


def _image_blocker(df):
	if df.get("fieldtype") != "Image":
		return None
	src = df.get("image_url") or ""
	if src.startswith(("http://", "https://")):
		return _("Remote image URL")
	return None


def _walk(layout):
	zones = [
		(_("Header"), layout.get("header")),
		(_("Footer"), layout.get("footer")),
	] + [(s.get("label") or _("Section"), s) for s in layout.get("sections") or [] if isinstance(s, dict)]
	for where, zone in zones:
		if not isinstance(zone, dict):
			continue
		yield where, zone
		for column in zone.get("columns") or []:
			for df in (column or {}).get("fields") or []:
				if isinstance(df, dict):
					yield where, df


def typst_font_paths() -> list[str]:
	"""Directories Typst loads fonts from — the site's cache plus system fonts."""
	import os

	path = frappe.get_site_path("private", "files", "typst_fonts")
	return [os.path.abspath(path)] if os.path.isdir(path) else []


def ensure_typst_fonts(family: str | None):
	"""Fetch the format's Google Font as TTFs into the site's font cache.

	Best-effort: offline or unknown families log once and Typst falls back to
	its bundled font instead of failing the print."""
	import os

	if not family or family == "Default":
		return
	safe_family = re.sub(r"[^A-Za-z0-9 _-]", "", family).replace(" ", "_")
	if not safe_family:
		return
	root = frappe.get_site_path("private", "files", "typst_fonts")
	target = os.path.join(root, safe_family)
	if os.path.isdir(target) and os.listdir(target):
		return
	try:
		import requests

		urls = []
		for weight in (400, 500, 600, 700):
			css = requests.get(
				"https://fonts.googleapis.com/css2",
				params={"family": f"{family}:wght@{weight}"},
				headers={"User-Agent": "Mozilla/4.0"},
				timeout=5,
			).text
			found = re.findall(r"https://[^)]+\.ttf", css)
			if found:
				urls.append((weight, found[0]))
		if not urls:
			return
		os.makedirs(target, exist_ok=True)
		for weight, url in urls:
			ttf = requests.get(url, timeout=10).content
			# safe_family is allowlist-sanitized above; the path cannot leave the cache dir
			# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
			with open(os.path.join(target, f"{safe_family}-{weight}.ttf"), "wb") as f:
				f.write(ttf)
	except Exception:
		frappe.log_error(title=f"Typst font fetch failed: {family}")


def q(value) -> str:
	"""A Typst string literal — every doc value crosses as a quoted string, so
	document content can never be interpreted as Typst markup."""
	return json.dumps(str(value if value is not None else ""))


def _text_value(html_ish: str) -> str:
	"""Formatted values may carry markup (Text Editor, address_display); keep the
	line structure, drop the tags."""
	value = str(html_ish or "")
	if "<" not in value:
		return value
	value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
	value = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", value, flags=re.I)
	value = re.sub(r"<[^>]+>", "", value)
	return unescape_html(value).strip()


class TypstEmitter:
	def __init__(self, generator):
		self.generator = generator
		self.doc = generator.doc
		self.print_format = generator.print_format
		self.layout = generator.layout
		self.assets: dict[str, bytes] = {}

	# ── document ────────────────────────────────────────────────

	def prepare(self):
		"""Render zones and body once; assets register as a side effect."""
		if hasattr(self, "header_src"):
			return
		header_zone = self.layout.get("header")
		self.header_src = self._section(header_zone, zone=True) if isinstance(header_zone, dict) else ""
		self.body_src = "\n".join(
			part for part in (self._section(s) for s in self.layout.get("sections") or []) if part
		)
		footer_zone = self.layout.get("footer")
		self.footer_src = self._section(footer_zone, zone=True) if isinstance(footer_zone, dict) else ""

	def measure_source(self) -> str:
		"""A document whose only output is the measured height of each zone, read
		back with typst.query — how the top/bottom margins learn to make room."""
		self.prepare()
		pf = self.print_format
		inner = round(
			210 - (frappe.utils.flt(pf.margin_left) or 15) - (frappe.utils.flt(pf.margin_right) or 15), 2
		)
		lines = ["#set page(width: 210mm, height: 297mm)", self._text_setup(), ""]
		for label, src in (("pfhdr", self.header_src), ("pfftr", self.footer_src)):
			if src:
				lines.append(
					f"#context [#metadata(measure(box(width: {inner}mm)[{src}]).height.pt()) <{label}>]"
				)
		return "\n".join(lines)

	def emit(self, repeat_header_footer=False, header_height_pt=0, footer_height_pt=0):
		"""The document source. With repeat on, the zones move into Typst's page
		header/footer slots (repeated on every page, like Chromium's repeating
		frame) and the margins grow by their measured heights."""
		self.prepare()
		in_page_header = bool(repeat_header_footer and self.header_src)
		in_page_footer = bool(repeat_header_footer and self.footer_src)
		lines = [
			self._page_setup(
				header_zone=self.header_src if in_page_header else None,
				footer_zone=self.footer_src if in_page_footer else None,
				header_height_pt=header_height_pt,
				footer_height_pt=footer_height_pt,
			),
			self._text_setup(),
			"",
		]
		if self.header_src and not in_page_header:
			lines.append(self.header_src)
		lines.append(self.body_src)
		if self.footer_src and not in_page_footer:
			lines.append(self.footer_src)
		return "\n".join(line for line in lines if line), self.assets

	def _page_setup(self, header_zone=None, footer_zone=None, header_height_pt=0, footer_height_pt=0) -> str:
		pf = self.print_format
		top = frappe.utils.flt(pf.margin_top) or 15
		bottom = frappe.utils.flt(pf.margin_bottom) or 15
		top_expr = f"{top}mm + {round(header_height_pt + 12, 2)}pt" if header_zone else f"{top}mm"
		bottom_expr = f"{bottom}mm + {round(footer_height_pt + 12, 2)}pt" if footer_zone else f"{bottom}mm"
		margins = (
			f"(top: {top_expr}, bottom: {bottom_expr}, "
			f"left: {frappe.utils.flt(pf.margin_left) or 15}mm, "
			f"right: {frappe.utils.flt(pf.margin_right) or 15}mm)"
		)
		args = ["width: 210mm", "height: 297mm", f"margin: {margins}"]

		slots = {"header": [], "footer": []}
		position = PAGE_NUMBER_POSITIONS.get(pf.get("page_number") or "")
		if position:
			slot, align = position
			slots[slot].append(
				f'[#context [#set text(size: 7pt, fill: rgb("#6b7280"))\n'
				f"  #set align({align})\n"
				f'  #counter(page).display("1 of 1", both: true)]]'
			)
		if header_zone:
			slots["header"].append(f"[{header_zone}]")
		if footer_zone:
			slots["footer"].insert(0, f"[{footer_zone}]")

		for slot, parts in slots.items():
			if not parts:
				continue
			content = parts[0] if len(parts) == 1 else "stack(spacing: 6pt, " + ", ".join(parts) + ")"
			args.append(f"{slot}: {content}")
			if slot == "header":
				args.append("header-ascent: 8pt" if header_zone else "header-ascent: 30%")
			elif footer_zone:
				args.append("footer-descent: 8pt")
		return "#set page(" + ", ".join(args) + ")"

	def _text_setup(self) -> str:
		pf = self.print_format
		size_pt = round((frappe.utils.flt(pf.font_size) or 14) * PX_TO_PT, 2)
		args = [f"size: {size_pt}pt"]
		if pf.get("font") and pf.font != "Default":
			args.append(f'font: ({q(pf.font)}, "Libertinus Serif")')
		if pf.get("value_color"):
			args.append(f'fill: rgb("{pf.value_color}")')
		return "#set text(" + ", ".join(args) + ")"

	# ── sections ────────────────────────────────────────────────

	def _section(self, section, zone=False) -> str:
		if section.get("_hidden"):
			return ""
		columns = [c for c in section.get("columns") or [] if isinstance(c, dict)]
		if not columns:
			return ""
		rendered_columns = [self._column(section, c) for c in columns]
		if not any(rendered_columns):
			return ""

		grid = self._columns_grid(section, columns, rendered_columns)
		body = grid
		if section.get("label") and section.get("show_label") != "hide" and not zone:
			label = f"#text(size: 0.9em, weight: 600, {q(_(section['label']))})"
			body = f"#stack(spacing: 8pt,\n[{label}],\n[{body}])"

		block_args = self._section_block_args(section)
		out = f"#block({', '.join(block_args)})[\n{body}\n]"
		out = self._apply_style_effects(out, section.get("custom_style"))
		margin = section.get("margin") or {}
		top = round(frappe.utils.flt(margin.get("top")) * PX_TO_PT, 2)
		bottom = round(frappe.utils.flt(margin.get("bottom")) * PX_TO_PT, 2)
		if top:
			out = f"#v({top}pt)\n{out}"
		return out + f"\n#v({bottom + 6}pt)"

	def _section_block_args(self, section) -> list[str]:
		args = ["width: 100%"]
		if section.get("field_borders"):
			args.append('stroke: 0.6pt + rgb("#e5e7eb")')
			args.append("radius: 4pt")
			pad = frappe.utils.flt(section.get("cell_padding"), 0) or 8
			args.append(f"inset: {round(pad * PX_TO_PT, 2)}pt")
			args.append("clip: true")
		if section.get("background"):
			args.append(f'fill: rgb("{section["background"]}")')
		padding = section.get("padding") or {}
		if padding and not section.get("field_borders"):
			args.append(
				"inset: (top: {top}pt, bottom: {bottom}pt, left: {left}pt, right: {right}pt)".format(
					**{
						k: round(frappe.utils.flt(padding.get(k)) * PX_TO_PT, 2)
						for k in ("top", "bottom", "left", "right")
					}
				)
			)
		if section.get("radius") is not None and not section.get("field_borders"):
			args.append(f"radius: {round(frappe.utils.flt(section['radius']) * PX_TO_PT, 2)}pt")
		if section.get("keep_together"):
			args.append("breakable: false")
		return args

	def _columns_grid(self, section, columns, rendered_columns) -> str:
		gap = section.get("gap")
		style_gap = translate_custom_style(section.get("custom_style") or "")[0].get("gap")
		if style_gap is not None:
			gap_pt = style_gap
		else:
			gap_pt = round(frappe.utils.flt(gap if gap is not None else 20) * PX_TO_PT, 2)
		widths = []
		for column in columns:
			width = frappe.utils.flt(column.get("width"))
			widths.append(f"{width}fr" if width else "1fr")

		justify = section.get("justify")
		cells = [f"[{body or ''}]" for body in rendered_columns]
		if justify in ("space-between", "space-evenly", "center", "right-end"):
			widths = ["auto"] * len(columns)
			if justify == "space-between" and len(columns) > 1:
				spaced = []
				for i, cell in enumerate(cells):
					if i:
						spaced.append("[]")
					spaced.append(cell)
				widths = ["auto", "1fr"] * (len(columns) - 1) + ["auto"]
				cells = spaced
			elif justify == "right-end":
				widths = ["1fr", *(["auto"] * len(columns))]
				cells = ["[]", *cells]
			elif justify == "center":
				widths = ["1fr", *(["auto"] * len(columns)), "1fr"]
				cells = ["[]", *cells, "[]"]
			elif justify == "space-evenly":
				spaced, w = [], []
				for cell in cells:
					spaced += ["[]", cell]
					w += ["1fr", "auto"]
				spaced.append("[]")
				w.append("1fr")
				cells, widths = spaced, w

		if len(cells) == 1:
			return cells[0][1:-1]
		if section.get("field_borders") and section.get("grid_borders") != "rows":
			pad = round((frappe.utils.flt(section.get("cell_padding"), 0) or 8) * PX_TO_PT, 2)
			divided = [cells[0]]
			for cell in cells[1:]:
				divided.append(
					f'grid.cell(stroke: (left: 0.6pt + rgb("#e5e7eb")), inset: (left: {pad}pt))' + cell
				)
			return (
				f"#grid(columns: ({', '.join(widths)}), column-gutter: {pad}pt, align: top,\n"
				+ ",\n".join(divided)
				+ ")"
			)
		return (
			f"#grid(columns: ({', '.join(widths)}), column-gutter: {gap_pt}pt, align: top,\n"
			+ ",\n".join(cells)
			+ ")"
		)

	def _column(self, section, column) -> str:
		parts = [self._field(section, df) for df in column.get("fields") or []]
		parts = [p for p in parts if p]
		if not parts:
			return ""
		if section.get("field_borders") and section.get("grid_borders") != "columns" and len(parts) > 1:
			pad = round((frappe.utils.flt(section.get("cell_padding"), 0) or 8) * PX_TO_PT, 2)
			ruled = [
				f'#block(width: 100%, stroke: (bottom: 0.6pt + rgb("#e5e7eb")), inset: (bottom: {pad}pt))[{p}]'
				for p in parts[:-1]
			] + [parts[-1]]
			return f"#stack(spacing: {pad}pt,\n" + ",\n".join(f"[{p}]" for p in ruled) + ")"
		if len(parts) == 1:
			return parts[0]
		return "#stack(spacing: 8pt,\n" + ",\n".join(f"[{p}]" for p in parts) + ")"

	# ── fields ──────────────────────────────────────────────────

	def _field(self, section, df) -> str:
		if df.get("_hidden"):
			return ""
		body = self._field_body(section, df)
		if not body:
			return ""
		return self._apply_style_effects(body, df.get("custom_style"))

	def _apply_style_effects(self, body: str, style) -> str:
		if not isinstance(style, str) or not style.strip():
			return body
		effects, _unknown = translate_custom_style(style)
		if not effects:
			return body
		if effects.get("bold"):
			body = f"#text(weight: 700)[{body}]"
		strokes = []
		if effects.get("stroke_top"):
			strokes.append(f"top: {effects['stroke_top']}")
		if effects.get("stroke_bottom"):
			strokes.append(f"bottom: {effects['stroke_bottom']}")
		insets = []
		if effects.get("inset_top"):
			insets.append(f"top: {effects['inset_top']}pt")
		if effects.get("inset_bottom"):
			insets.append(f"bottom: {effects['inset_bottom']}pt")
		if strokes or insets:
			args = ["width: 100%"]
			if strokes:
				args.append(f"stroke: ({', '.join(strokes)})")
			if insets:
				args.append(f"inset: ({', '.join(insets)})")
			body = f"#block({', '.join(args)})[{body}]"
		if effects.get("space_before"):
			body = f"#v({effects['space_before']}pt)\n{body}"
		return body

	def _field_body(self, section, df) -> str:
		fieldtype = df.get("fieldtype") or "Data"
		if fieldtype == "Divider":
			return '#line(length: 100%, stroke: 0.6pt + rgb("#d1d5db"))'
		if fieldtype == "Spacer":
			height = frappe.utils.flt(df.get("height")) or 13
			return f"#v({round(height * PX_TO_PT, 2)}pt)"
		if fieldtype == "Table":
			return self._table(df)
		if fieldtype == "Barcode":
			return self._barcode(df)
		if fieldtype in ("Image", "Attach Image"):
			return self._image(df)
		if fieldtype == "Repeater":
			return self._repeater(df)
		return self._data_field(section, df)

	def _formatted_value(self, df):
		fieldname = df.get("fieldname")
		if not fieldname:
			return ""
		value = self.doc.get(fieldname)
		if value in (None, ""):
			return ""
		if df.get("fieldtype") == "Check":
			return _("Yes") if frappe.utils.cint(value) else _("No")
		return _text_value(self.doc.get_formatted(fieldname))

	def _data_field(self, section, df) -> str:
		value = self._formatted_value(df)
		if not value:
			return ""
		pf = self.print_format
		show_label = df.get("show_label") or "show"
		inline = show_label == "inline" or section.get("field_orientation") == "left-right"

		label_color = df.get("label_color") or pf.get("label_color") or "#6b7280"
		value_color = df.get("value_color")
		label = ""
		if show_label != "hide" and df.get("label"):
			label = f'#text(size: 0.85em, fill: rgb("{label_color}"), {q(_(df["label"]))})'
		value_args = [q(value)]
		if value_color:
			value_args.insert(0, f'fill: rgb("{value_color}")')
		value_text = f"#text({', '.join(value_args)})"

		align = df.get("align")
		if inline and label:
			gap = df.get("label_gap")
			gap_pt = round(frappe.utils.flt(gap) * PX_TO_PT, 2) if gap else 4
			if align in ("right",):
				body = f"#grid(columns: (1fr, auto), column-gutter: {gap_pt}pt, [{label}], [#align(right)[{value_text}]])"
			else:
				body = f"#grid(columns: (auto, 1fr), column-gutter: {gap_pt}pt, [{label}], [{value_text}])"
			return body
		gap_effect = translate_custom_style(df.get("custom_style") or "")[0].get("gap")
		spacing = gap_effect if gap_effect is not None else 4
		parts = [f"[{label}]"] if label else []
		parts.append(f"[{value_text}]")
		body = f"#stack(spacing: {spacing}pt,\n" + ",\n".join(parts) + ")" if len(parts) > 1 else value_text
		if align in ("center", "right"):
			return f"#align({align})[{body}]"
		return body

	def _asset(self, suffix: str, data: bytes) -> str:
		name = f"asset_{len(self.assets)}.{suffix}"
		self.assets[name] = data
		return name

	def _read_site_file(self, src: str) -> bytes | None:
		import base64
		import os

		if src.startswith("data:"):
			try:
				return base64.b64decode(src.split(",", 1)[1])
			except Exception:
				return None
		if src.startswith(("http://", "https://")):
			return None
		src = src.split("?", 1)[0]
		if src.startswith("/private/files/"):
			# private files are permission-gated through the File doctype — the
			# browser path enforces this over HTTP, so the direct read must too
			file_name = frappe.db.get_value("File", {"file_url": src}, "name")
			if not file_name or not frappe.has_permission("File", doc=file_name, ptype="read"):
				return None
			root, rel = frappe.get_site_path("private", "files"), src[len("/private/files/") :]
		elif src.startswith("/files/"):
			root, rel = frappe.get_site_path("public", "files"), src[len("/files/") :]
		elif src.startswith("/assets/"):
			root, rel = frappe.get_site_path("..", "assets"), src[len("/assets/") :]
		else:
			return None
		# the src is document data — never let it walk out of its root
		root = os.path.realpath(root)
		path = os.path.realpath(os.path.join(root, rel))
		if not path.startswith(root + os.sep):
			return None
		try:
			# audited: realpath containment above, File permission for private paths
			# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
			with open(path, "rb") as f:
				return f.read()
		except OSError:
			return None

	@staticmethod
	def _dimension(width) -> str | None:
		if width in (None, ""):
			return None
		value = str(width).strip()
		if value.endswith(("mm", "cm", "in", "pt")):
			return value
		if value.endswith("%"):
			return value
		if value.endswith("px"):
			value = value[:-2]
		try:
			return f"{round(float(value) * PX_TO_PT, 2)}pt"
		except ValueError:
			return None

	def _image(self, df) -> str:
		src = df.get("image_url") or (self.doc.get(df.get("fieldname")) if df.get("fieldname") else "")
		if not src:
			return ""
		data = self._read_site_file(str(src))
		if data is None:
			frappe.throw(
				_("The Typst renderer cannot embed this image: {0}").format(frappe.bold(str(src)[:100])),
				title=_("Typst renderer unavailable"),
			)
		suffix = str(src).split("?", 1)[0].rsplit(".", 1)[-1].lower()
		if suffix not in ("png", "jpg", "jpeg", "svg", "gif", "webp"):
			suffix = "png"
		name = self._asset(suffix, data)
		width = self._dimension(df.get("width")) or "100%"
		body = f'#image("{name}", width: {width})'
		if df.get("align") in ("center", "right"):
			return f"#align({df['align']})[{body}]"
		return body

	def _barcode(self, df) -> str:
		data_uri = df.get("_qr_data_uri")
		if not data_uri:
			return ""
		data = self._read_site_file(data_uri)
		if data is None:
			return ""
		name = self._asset("svg", data)
		width = self._dimension(df.get("width")) or "30mm"
		body = f'#image("{name}", width: {width})'
		if df.get("align") in ("center", "right"):
			return f"#align({df['align']})[{body}]"
		return body

	def _repeater(self, df) -> str:
		source = df.get("source")
		rows = df.get("_rows") if df.get("_rows") is not None else (self.doc.get(source) if source else None)
		rows = rows or []
		columns = df.get("repeater_columns") or []
		if not rows or not columns:
			return ""

		widths = []
		for col in columns:
			width = frappe.utils.flt(col.get("width"))
			widths.append(f"{round(width, 2)}fr" if width else "1fr")
		aligns = [
			col.get("align") if col.get("align") in ("left", "center", "right") else "left" for col in columns
		]

		cells = []
		for row in rows:
			for col in columns:
				parts = []
				for tok in col.get("template") or []:
					if not isinstance(tok, dict):
						continue
					if tok.get("t") == "f":
						parts.append(_text_value(row.get_formatted(tok.get("v"))))
					else:
						parts.append(str(tok.get("v") or ""))
				text = "".join(parts)
				color = col.get("color")
				fill = (
					f'fill: rgb("{color}"), '
					if isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color)
					else ""
				)
				cells.append(f"[#text({fill}{q(text)})]" if text else "[]")

		label = ""
		if df.get("label") and (df.get("show_label") or "show") != "hide":
			label_color = self.print_format.get("label_color") or "#6b7280"
			label = f'#text(size: 0.85em, fill: rgb("{label_color}"), {q(_(df["label"]))})\n#v(3pt)\n'
		return (
			label
			+ f"#table(columns: ({', '.join(widths)}), align: ({', '.join(aligns)},), stroke: none, inset: 4pt,\n"
			+ ",\n".join(cells)
			+ ")"
		)

	# ── tables ──────────────────────────────────────────────────

	def _table(self, df) -> str:
		columns = df.get("table_columns") or []
		if not columns:
			return ""
		rows = df.get("_rows") if df.get("_rows") is not None else self.doc.get(df.get("fieldname"))
		rows = rows or []
		if not rows:
			return ""

		widths = []
		for col in columns:
			width = frappe.utils.flt(col.get("width"))
			widths.append(f"{round(width, 2)}fr" if width else "1fr")
		aligns = [
			"right" if (col.get("fieldtype") in RIGHT_ALIGNED_FIELDTYPES) else "left" for col in columns
		]

		header_cells = [
			f"#text(weight: 600, size: 0.85em, {q(_(col.get('label') or ''))})" for col in columns
		]
		body_cells = []
		for row in rows:
			for col in columns:
				body_cells.append(self._table_cell(row, col))

		label = ""
		if df.get("show_label") != "hide" and df.get("label"):
			label_color = self.print_format.get("label_color") or "#6b7280"
			label = f'#text(size: 0.85em, fill: rgb("{label_color}"), {q(_(df["label"]))})\n#v(3pt)\n'

		bordered = df.get("table_bordered")
		stroke = '0.6pt + rgb("#e5e7eb")' if bordered is None or bordered else "none"
		header_bg = df.get("table_header_bg") or "#f3f4f6"
		show_header = df.get("table_header") is None or df.get("table_header")

		parts = [
			f"columns: ({', '.join(widths)})",
			f"align: ({', '.join(aligns)},)",
			f"stroke: {stroke}",
			f"inset: {round((frappe.utils.flt(df.get('table_cell_padding'), 0) or 8) * PX_TO_PT, 2)}pt",
		]
		if show_header:
			parts.append(f'fill: (_, row) => if row == 0 {{ rgb("{header_bg}") }}')
			cells = ["table.header(" + ", ".join(f"[{cell}]" for cell in header_cells) + ")"]
		else:
			cells = []
		cells += [f"[{cell}]" for cell in body_cells]
		return label + "#table(" + ", ".join(parts) + ",\n" + ",\n".join(cells) + ")"

	def _table_cell(self, row, col) -> str:
		merged = col.get("merged_fields")
		if merged:
			# the column's own field is the implicit primary line (Table.html:39)
			merged = [{"fieldname": col.get("fieldname"), "fieldtype": col.get("fieldtype")}, *merged]
			lines = []
			first_text = True
			for mf in merged:
				fieldname = mf.get("fieldname")
				if not fieldname or mf.get("fieldtype") in ("Attach Image", "Attach"):
					continue
				value = _text_value(row.get_formatted(fieldname))
				if not value:
					continue
				if first_text:
					lines.append(f"#text(weight: 500, {q(value)})")
					first_text = False
				else:
					lines.append(f'#text(size: 0.85em, fill: rgb("#6b7280"), {q(value)})')
			if not lines:
				return ""
			if len(lines) == 1:
				return lines[0]
			if col.get("merge_direction") == "horizontal":
				return " #h(3pt) ".join(lines)
			return "#stack(spacing: 3pt, " + ", ".join(f"[{line}]" for line in lines) + ")"
		fieldname = col.get("fieldname")
		if not fieldname:
			return ""
		if fieldname == "idx":
			return f"#text({q(row.get('idx'))})"
		return f"#text({q(_text_value(row.get_formatted(fieldname)))})"
