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
BLOCKER_FIELDTYPES = {
	"HTML": _("Custom HTML block"),
	"Field Template": _("Field Template (Jinja HTML)"),
	"Image": _("Image block"),
	"Barcode": _("Barcode"),
	"Repeater": _("Repeater block"),
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
			key = ("custom_style", where)
			if key not in seen:
				seen.add(key)
				blockers.append(_("Custom CSS on {0}").format(where))
		reason = BLOCKER_FIELDTYPES.get(node.get("fieldtype"))
		if reason and reason not in seen:
			seen.add(reason)
			blockers.append(reason)
	return blockers


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

	# ── document ────────────────────────────────────────────────

	def emit(self) -> str:
		lines = [self._page_setup(), self._text_setup(), ""]

		header_zone = self.layout.get("header")
		if isinstance(header_zone, dict):
			lines.append(self._section(header_zone, zone=True))
		for section in self.layout.get("sections") or []:
			lines.append(self._section(section))
		footer_zone = self.layout.get("footer")
		if isinstance(footer_zone, dict):
			lines.append(self._section(footer_zone, zone=True))
		return "\n".join(line for line in lines if line)

	def _page_setup(self) -> str:
		pf = self.print_format
		margins = (
			f"(top: {frappe.utils.flt(pf.margin_top) or 15}mm, "
			f"bottom: {frappe.utils.flt(pf.margin_bottom) or 15}mm, "
			f"left: {frappe.utils.flt(pf.margin_left) or 15}mm, "
			f"right: {frappe.utils.flt(pf.margin_right) or 15}mm)"
		)
		args = ["width: 210mm", "height: 297mm", f"margin: {margins}"]
		position = PAGE_NUMBER_POSITIONS.get(pf.get("page_number") or "")
		if position:
			slot, align = position
			counter = (
				f'context [#set text(size: 7pt, fill: rgb("#6b7280"))\n'
				f"  #set align({align})\n"
				f'  #counter(page).display("1 of 1", both: true)]'
			)
			args.append(f"{slot}: {counter}")
			if slot == "header":
				args.append("header-ascent: 30%")
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
		if section.get("label") and not any(rendered_columns):
			return ""
		if not any(rendered_columns) and not zone:
			return ""

		grid = self._columns_grid(section, columns, rendered_columns)
		body = grid
		if section.get("label") and section.get("show_label") != "hide" and not zone:
			label = f"#text(size: 0.9em, weight: 600, {q(_(section['label']))})"
			body = f"#stack(spacing: 8pt,\n[{label}],\n[{body}])"

		block_args = self._section_block_args(section)
		out = f"#block({', '.join(block_args)})[\n{body}\n]"
		return out + "\n#v(8pt)"

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
		margin = section.get("margin") or {}
		if margin:
			args.append(
				"outset: (top: -{top}pt, bottom: -{bottom}pt)".format(
					top=round(frappe.utils.flt(margin.get("top")) * PX_TO_PT, 2),
					bottom=round(frappe.utils.flt(margin.get("bottom")) * PX_TO_PT, 2),
				)
			)
		if section.get("radius") is not None and not section.get("field_borders"):
			args.append(f"radius: {round(frappe.utils.flt(section['radius']) * PX_TO_PT, 2)}pt")
		if section.get("keep_together"):
			args.append("breakable: false")
		return args

	def _columns_grid(self, section, columns, rendered_columns) -> str:
		gap = section.get("gap")
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
		if len(parts) == 1:
			return parts[0]
		return "#stack(spacing: 8pt,\n" + ",\n".join(f"[{p}]" for p in parts) + ")"

	# ── fields ──────────────────────────────────────────────────

	def _field(self, section, df) -> str:
		if df.get("_hidden"):
			return ""
		fieldtype = df.get("fieldtype") or "Data"
		if fieldtype == "Divider":
			return '#line(length: 100%, stroke: 0.6pt + rgb("#d1d5db"))'
		if fieldtype == "Spacer":
			height = frappe.utils.flt(df.get("height")) or 13
			return f"#v({round(height * PX_TO_PT, 2)}pt)"
		if fieldtype == "Table":
			return self._table(df)
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
		parts = [f"[{label}]"] if label else []
		parts.append(f"[{value_text}]")
		body = "#stack(spacing: 4pt,\n" + ",\n".join(parts) + ")" if len(parts) > 1 else value_text
		if align in ("center", "right"):
			return f"#align({align})[{body}]"
		return body

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
			lines = []
			for mf in merged:
				fieldname = mf.get("fieldname")
				if not fieldname:
					continue
				value = _text_value(row.get_formatted(fieldname))
				if value:
					style = mf.get("style") or "primary"
					size = "0.85em" if style != "primary" else "1em"
					fill = ', fill: rgb("#6b7280")' if style != "primary" else ""
					lines.append(f"#text(size: {size}{fill}, {q(value)})")
			if not lines:
				return ""
			if len(lines) == 1:
				return lines[0]
			return "#stack(spacing: 3pt, " + ", ".join(f"[{line}]" for line in lines) + ")"
		fieldname = col.get("fieldname")
		if not fieldname:
			return ""
		if fieldname == "idx":
			return f"#text({q(row.get('idx'))})"
		return f"#text({q(_text_value(row.get_formatted(fieldname)))})"
