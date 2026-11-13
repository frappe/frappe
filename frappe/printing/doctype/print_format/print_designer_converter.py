# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import html
import json
import re

import frappe
from frappe import _
from frappe.model.naming import append_number_if_name_exists
from frappe.model.rename_doc import get_link_fields, update_link_field_values
from frappe.utils import cint, escape_html, flt

PX_PER_MM = 96 / 25.4
TABLE_TEXT_SCALE = 0.9
COLUMN_PADDING = 15
SIDE_MARGIN = re.compile(r"margin-(left|right):\s*(-?\d+(?:\.\d+)?)%;\s*")
JINJA = re.compile(r"{{|{%")
CSS_PROPERTIES = {
	"fontSize": "font-size",
	"fontWeight": "font-weight",
	"fontStyle": "font-style",
	"fontFamily": "font-family",
	"color": "color",
	"textAlign": "text-align",
	"textDecoration": "text-decoration",
	"textTransform": "text-transform",
	"lineHeight": "line-height",
	"letterSpacing": "letter-spacing",
	"backgroundColor": "background-color",
	"borderWidth": "border-width",
	"borderStyle": "border-style",
	"borderColor": "border-color",
	"borderRadius": "border-radius",
	"paddingTop": "padding-top",
	"paddingRight": "padding-right",
	"paddingBottom": "padding-bottom",
	"paddingLeft": "padding-left",
	"whiteSpace": "white-space",
}
PAGE_NUMBER_FIELDS = {"page": '<span class="page"></span>', "topage": '<span class="topage"></span>'}
BARCODE_FORMATS = {"qrcode": "QR", "qr": "QR", "code128": "CODE128", "code39": "CODE39"}


def is_print_designer_format(doc) -> bool:
	return bool(
		doc.get("print_designer")
		and (doc.get("print_designer_print_format") or doc.get("print_designer_body"))
	)


def convert_print_designer_format(doc) -> tuple[dict, list[str]]:
	"""Return a print format editor layout for a Print Designer format, and notes on
	what could not be carried over exactly."""
	return PrintDesignerConverter(doc).convert()


def converted_values(doc) -> tuple[dict, list[str]]:
	"""The fields that make a Print Designer format an editor format, and notes on
	what could not be carried over exactly."""
	layout, notes = convert_print_designer_format(doc)
	values = {
		"print_designer": 0,
		"print_format_builder_beta": 1,
		"format_data": json.dumps(layout),
		"font": converted_font(doc),
		**converted_margins(doc),
	}
	return values, notes


@frappe.whitelist(methods=["POST"])
def convert(print_format: str) -> dict:
	"""Turn a Print Designer format into an editor format under the same name. The
	Print Designer fields stay on the record, like classic_format_data. A standard format
	belongs to its app, so it gets an editor copy instead."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Print Format", print_format)
	if not is_print_designer_format(doc):
		frappe.throw(_("{0} is not a Print Designer format.").format(frappe.bold(print_format)))
	values, notes = converted_values(doc)
	if doc.standard == "Yes":
		copy = editor_copy(doc)
		if not copy:
			copy = frappe.copy_doc(doc)
			copy.update({"standard": "No", "disabled": 0, "converted_from": doc.name, **values})
			copy.insert(
				set_name=append_number_if_name_exists("Print Format", f"{doc.name} (Editor)", separator=" ")
			)
		target = copy
	else:
		frappe.db.set_value("Print Format", doc.name, values)
		frappe.clear_cache(doctype=doc.doc_type)
		target = doc
	if notes:
		target.add_comment("Comment", "<br>".join(escape_html(n) for n in notes))
	usage = print_format_usage(doc.name) if target is not doc else []
	return {"name": target.name, "notes": notes, "usage": usage}


@frappe.whitelist(methods=["POST"])
def use_editor_copy(print_format: str) -> None:
	"""Point the doctype defaults and every link to a standard format at its editor copy."""
	frappe.only_for("System Manager")
	copy = editor_copy(frappe.get_doc("Print Format", print_format))
	if not copy:
		frappe.throw(_("{0} has no editor copy.").format(frappe.bold(print_format)))
	move_print_format_usage(print_format, copy.name)


def editor_copy(doc):
	"""The editor copy made from a standard Print Designer format, if it still exists."""
	name = frappe.db.get_value(
		"Print Format",
		{"converted_from": doc.name, "doc_type": doc.doc_type, "print_format_builder_beta": 1},
		"name",
		order_by="creation asc",
	)
	return frappe.get_doc("Print Format", name) if name else None


def move_print_format_usage(old: str, new: str) -> None:
	update_link_field_values(print_format_link_fields(), old, new, "Print Format")
	doctypes = frappe.get_all(
		"Property Setter", {"property": "default_print_format", "value": old}, pluck="doc_type"
	)
	frappe.db.set_value("Property Setter", {"property": "default_print_format", "value": old}, "value", new)
	doctypes += frappe.get_all("DocType", {"default_print_format": old}, pluck="name")
	frappe.db.set_value("DocType", {"default_print_format": old}, "default_print_format", new)
	for doctype in set(doctypes):
		frappe.clear_cache(doctype=doctype)


def print_format_link_fields() -> list[dict]:
	return [f for f in get_link_fields("Print Format") if f["parent"] != "Customize Form"]


def print_format_usage(print_format: str) -> list[str]:
	"""Where a print format is picked: doctype defaults, and documents or settings that link to it."""
	defaults = frappe.get_all(
		"Property Setter", {"property": "default_print_format", "value": print_format}, pluck="doc_type"
	) + frappe.get_all("DocType", {"default_print_format": print_format}, pluck="name")
	usage = [_("Default for {0}").format(_(doctype)) for doctype in sorted(set(defaults))]
	for field in print_format_link_fields():
		if field["issingle"]:
			count = int(frappe.db.get_single_value(field["parent"], field["fieldname"]) == print_format)
		else:
			count = frappe.db.count(field["parent"], {field["fieldname"]: print_format})
		if count:
			usage.append(_("{0}: {1}").format(_(field["parent"]), count))
	return usage


def converted_margins(doc) -> dict:
	settings = load_json(doc.get("print_designer_settings")) or {}
	page = settings.get("page") or {}
	margins = {}
	for field, key in (
		("margin_top", "marginTop"),
		("margin_bottom", "marginBottom"),
		("margin_left", "marginLeft"),
		("margin_right", "marginRight"),
	):
		if key in page:
			margins[field] = round(flt(page[key]) / PX_PER_MM, 1)
	return margins


def converted_font(doc) -> str | None:
	settings = load_json(doc.get("print_designer_settings")) or {}
	text = ((settings.get("globalStyles") or {}).get("staticText") or {}).get("style") or {}
	return text.get("fontFamily") or None


def has_side_by_side_overlap(elements: list[dict]) -> bool:
	"""Two elements share some height but sit next to each other, like text beside a tall image."""
	for i, a in enumerate(elements):
		for b in elements[i + 1 :]:
			a_top, b_top = flt(a.get("startY")), flt(b.get("startY"))
			a_left, b_left = flt(a.get("startX")), flt(b.get("startX"))
			if (
				a_top < b_top + flt(b.get("height")) - 2
				and b_top < a_top + flt(a.get("height")) - 2
				and (a_left + flt(a.get("width")) <= b_left + 2 or b_left + flt(b.get("width")) <= a_left + 2)
				and abs(a_top - b_top) > 6
			):
				return True
	return False


def load_json(value):
	if not value:
		return None
	if isinstance(value, dict | list):
		return value
	try:
		return json.loads(value)
	except ValueError:
		return None


class PrintDesignerConverter:
	def __init__(self, doc):
		self.doc = doc
		self.meta = frappe.get_meta(doc.doc_type)
		self.settings = load_json(doc.get("print_designer_settings")) or {}
		self.page = self.settings.get("page") or {}
		self.global_styles = self.settings.get("globalStyles") or {}
		self.notes = []
		self.counter = 0

	def convert(self) -> tuple[dict, list[str]]:
		compiled = load_json(self.doc.get("print_designer_print_format"))
		if compiled:
			header = self.first_page(compiled.get("header"))
			body = (compiled.get("body") or [{}])[0].get("childrens") or []
			footer = self.first_page(compiled.get("footer"))
		else:
			header, body, footer = (
				((load_json(self.doc.get(f"print_designer_{zone}")) or [{}])[0] or {}).get("childrens") or []
				for zone in ("header", "body", "footer")
			)
			self.notes.append(_("No row and column layout was saved, so rows were grouped by position."))

		layout = {
			"header": self.zone(header, flt(self.page.get("headerHeight"))),
			"sections": self.sections(body),
			"footer": self.zone(footer, flt(self.page.get("footerHeight"))),
			"letter_head": "",
		}
		if setup := (self.settings.get("userProvidedJinja") or "").strip():
			layout["global_variables"] = setup
		if page := self.page_settings():
			layout["page"] = page
		return layout, self.notes

	def first_page(self, zone) -> list:
		if isinstance(zone, list):
			return zone
		zone = zone or {}
		pages = [zone.get(k) for k in ("firstPage", "oddPage", "evenPage", "lastPage")]
		if any(p and p != pages[0] for p in pages[1:]):
			self.notes.append(
				_("The header or footer differs between pages; the first page's version was kept.")
			)
		return pages[0] or []

	def page_settings(self) -> dict | None:
		page = {}
		size = (self.settings.get("currentPageSize") or "").lower()
		sizes = frappe.get_meta("Print Settings").get_field("pdf_page_size").options.split("\n")
		if match := next((s for s in sizes if s.lower() == size and s != "Custom"), None):
			page["size"] = match
		elif size == "custom":
			self.notes.append(_("The custom paper size was not kept; set the paper size in the editor."))
		width, height = flt(self.page.get("width")), flt(self.page.get("height"))
		if width and height and width > height:
			page["orientation"] = "Landscape"
		return page or None

	def styled(self, element, part="style") -> dict:
		"""The element's style on top of Print Designer's default style for its kind."""
		kind = element.get("type")
		if kind == "text":
			kind = "dynamicText" if element.get("isDynamic") else "staticText"
		return {**((self.global_styles.get(kind) or {}).get(part) or {}), **(element.get(part) or {})}

	def rule(self, element) -> tuple[str, str] | None:
		"""The side and colour of the one border a drawn box shows, when it is a line."""
		if element.get("type") != "rectangle" or (element.get("layoutType") and element.get("childrens")):
			return None
		style = {
			**((self.global_styles.get("rectangle") or {}).get("style") or {}),
			**(element.get("style") or {}),
		}
		if flt(re.sub(r"[^\d.]", "", str(style.get("borderWidth") or "0")) or 0) <= 0:
			return None
		visible = [
			side
			for side in ("Top", "Right", "Bottom", "Left")
			if style.get(f"border{side}Style", style.get("borderStyle")) not in ("hidden", "none")
		]
		if len(visible) != 1 or visible[0] not in ("Top", "Bottom"):
			if len(visible) > 1:
				self.notes.append(_("A box border was left out; add it again in the editor."))
			return None
		return visible[0].lower(), style.get("borderColor") or "#000000"

	def divider(self, color, gap=0) -> dict:
		return {
			"label": "Divider",
			"fieldname": self.name("divider"),
			"fieldtype": "Divider",
			"custom": 1,
			"custom_style": f"margin: {round(max(gap, 0))}px 0 0; border-bottom-color: {color};",
		}

	def content_width(self) -> float:
		width = flt(self.page.get("width")) or 793.7
		return max(width - flt(self.page.get("marginLeft")) - flt(self.page.get("marginRight")), 1)

	# ----- structure ------------------------------------------------------------

	def zone(self, elements, height=0) -> dict:
		earlier_notes = len(self.notes)
		sections = self.sections(elements)
		gap = None
		if len(sections) == 1:
			columns = sections[0]["columns"]
			gap = sections[0].get("gap")
		elif all(len(s["columns"]) == 1 for s in sections):
			fields = []
			for section in sections:
				section_fields = section["columns"][0]["fields"]
				if section_fields and (margin := section.get("margin")):
					add_gap(section_fields[0], flt(margin.get("top")))
				fields.extend(section_fields)
			columns = [{"label": "", "fields": fields}]
		else:
			del self.notes[earlier_notes:]
			rows = self.overlapping_rows(
				sorted(elements, key=lambda e: (flt(e.get("startY")), flt(e.get("startX"))))
			)
			html = "".join(self.row_html(row) for row in rows)
			columns = [{"label": "", "fields": [self.html_node(html)]}]
		bottom = max((flt(e.get("startY")) + flt(e.get("height")) for e in elements), default=0)
		if elements and height - bottom > 2:
			for column in columns:
				column["fields"].append(
					{
						"label": "Spacer",
						"fieldname": self.name("spacer"),
						"fieldtype": "Spacer",
						"custom": 1,
						"height": round(height - bottom),
					}
				)
		return {"columns": columns} if gap is None else {"columns": columns, "gap": gap}

	def row_html(self, row: list[dict], total: float = 0, origin: float = 0) -> str:
		total = total or self.content_width()
		compiled = len(row) == 1 and row[0].get("layoutType") == "row"
		children = self.printed(row[0].get("childrens") or []) if compiled else row
		top = 0 if compiled else min(flt(e.get("startY")) for e in row)
		height = (
			flt(row[0].get("height"))
			if compiled
			else max(flt(e.get("startY")) + flt(e.get("height")) for e in row) - top
		)
		parts = []
		if not compiled:
			children = []
			for stack in self.stacks(row):
				if len(stack) == 1:
					children.append(stack[0])
					continue
				left = min(flt(e.get("startX")) for e in stack)
				right = max(flt(e.get("startX")) + flt(e.get("width")) for e in stack)
				inner, cursor = "", top
				for start, end, html, fixed in self.stack_pieces(stack, right - left, left):
					style = f"margin-top: {round(max(start - cursor, 0))}px;"
					if fixed and end > max(start, cursor):
						style += f" min-height: {round(end - max(start, cursor))}px;"
					inner += f'<div style="{style}">{html}</div>'
					cursor = max(cursor, end)
				parts.append(
					(
						left,
						f'<div style="flex: 0 1 {round((right - left) / total * 100, 1)}%; min-width: 0; '
						f'overflow-wrap: anywhere;">{inner}</div>',
					)
				)
		for child in sorted(children, key=lambda c: flt(c.get("startX"))):
			inner = "".join(self.element_html(e) for e in self.flatten([child]))
			nested = child.get("childrens") if child.get("layoutType") == "column" else None
			offset = min(flt(c.get("startY")) for c in nested) if nested else flt(child.get("startY")) - top
			fits_content = child.get("type") == "text" and not child.get("isFixedSize")
			basis = "auto" if fits_content else f"{round(flt(child.get('width')) / total * 100, 1)}%"
			parts.append(
				(
					flt(child.get("startX")),
					f'<div style="flex: 0 1 {basis}; min-width: 0; '
					f'overflow-wrap: anywhere; padding-top: {round(max(offset, 0))}px;">{inner}</div>',
				)
			)
		parts.sort(key=lambda p: p[0])
		if parts and (indent := round(parts[0][0] - (0 if compiled else origin), 1)) > 0:
			parts[0] = (parts[0][0], parts[0][1].replace('style="', f'style="margin-left: {indent}px; ', 1))
		return (
			f'<div style="display: flex; justify-content: space-between; min-height: {round(height)}px;">'
			+ "".join(part for _left, part in parts)
			+ "</div>"
		)

	def stack_pieces(
		self, stack: list[dict], width: float, origin: float = 0
	) -> list[tuple[float, float, str, bool]]:
		pieces = []
		for band in self.overlapping_rows(
			sorted(stack, key=lambda e: (flt(e.get("startY")), flt(e.get("startX"))))
		):
			if len(self.stacks(band)) > 1:
				start = min(flt(e.get("startY")) for e in band)
				end = max(flt(e.get("startY")) + flt(e.get("height")) for e in band)
				pieces.append((start, end, self.row_html(band, width, origin), False))
				continue
			for element in sorted(band, key=lambda e: flt(e.get("startY"))):
				start, height = flt(element.get("startY")), flt(element.get("height"))
				html = "".join(self.element_html(e) for e in self.flatten([element]))
				fixed = element.get("type") in ("text", "rectangle") and not element.get("isDynamicHeight")
				pieces.append((start, start + height, html, fixed))
		return pieces

	def stacks(self, elements: list[dict]) -> list[list[dict]]:
		"""Elements that overlap horizontally, so they print one under the other."""
		stacks = []
		for element in sorted(elements, key=lambda e: flt(e.get("startX"))):
			left = flt(element.get("startX"))
			if stacks and left < stacks[-1][1] - 2:
				stacks[-1][0].append(element)
				stacks[-1][1] = max(stacks[-1][1], left + flt(element.get("width")))
			else:
				stacks.append([[element], left + flt(element.get("width"))])
		return [stack for stack, _right in stacks]

	def sections(self, elements) -> list[dict]:
		elements = sorted(elements or [], key=lambda e: (flt(e.get("startY")), flt(e.get("startX"))))
		sections, previous_bottom = [], 0
		for row in self.overlapping_rows(elements):
			top = min(flt(e.get("startY")) for e in row)
			section = {"label": "", "columns": self.columns(row, top if sections else 0)}
			tile_columns(section, self.content_width())
			gap = top - previous_bottom
			if sections and gap > 4:
				section["margin"] = {"top": round(gap), "right": 0, "bottom": 0, "left": 0}
			if any(c["fields"] for c in section["columns"]):
				sections.append(section)
			previous_bottom = max(flt(e.get("startY")) + flt(e.get("height")) for e in row)
		return sections

	def overlapping_rows(self, elements: list[dict]) -> list[list[dict]]:
		"""Rows that a tall element spans are one band, so the elements beside it
		stay next to it instead of starting below it."""
		bands, bottom = [], 0
		for band in self.rows(elements):
			top = min(flt(e.get("startY")) for e in band)
			if (
				bands
				and top < bottom - 2
				and band[0].get("layoutType") != "row"
				and bands[-1][0].get("layoutType") != "row"
			):
				bands[-1].extend(band)
			else:
				bands.append(list(band))
			bottom = max(bottom, *(flt(e.get("startY")) + flt(e.get("height")) for e in band))
		return bands

	def rows(self, elements) -> list[list[dict]]:
		"""Group elements into horizontal bands: a compiled row rectangle is one band,
		loose elements share a band when their tops line up."""
		bands = []
		for element in elements:
			if element.get("layoutType") == "row":
				bands.append([element])
				continue
			top = flt(element.get("startY"))
			if bands and bands[-1][0].get("layoutType") != "row":
				first = bands[-1][0]
				tolerance = max(6, 0.5 * min(flt(element.get("height")), flt(first.get("height"))))
				if abs(top - flt(first.get("startY"))) <= tolerance:
					bands[-1].append(element)
					continue
			bands.append([element])
		return bands

	def columns(self, row, top=0) -> list[dict]:
		total = self.content_width()
		if len(row) == 1 and row[0].get("layoutType") == "row":
			children = row[0].get("childrens") or []
			if children and all(
				c.get("type") == "rectangle" and c.get("layoutType") == "column" for c in children
			):
				return [
					{
						"label": "",
						"width": round(flt(c.get("width")) / total * 100, 1),
						"fields": self.element_fields(c, flt(c.get("width"))),
					}
					for c in sorted(self.printed(children), key=lambda c: flt(c.get("startX")))
				]
			row = children
			top = 0
		if (
			any(flt(e.get("width")) > 0.6 * total for e in row)
			and len(row) > 1
			and not has_side_by_side_overlap(row)
		):
			return [{"label": "", "fields": self.free_layout(row, total, top=top)}]
		return self.columns_by_position(row, total, top)

	def columns_by_position(self, elements, total, top=0) -> list[dict]:
		groups = []
		for element in sorted(elements, key=lambda e: flt(e.get("startX"))):
			left = flt(element.get("startX"))
			right = left + flt(element.get("width"))
			if groups and left < groups[-1]["right"] - 2:
				groups[-1]["items"].append(element)
				groups[-1]["right"] = max(groups[-1]["right"], right)
			else:
				groups.append({"left": left, "right": right, "items": [element]})
		columns, cursor = [], 0
		for i, group in enumerate(groups):
			if group["left"] - cursor > 8:
				columns.append(
					{"label": "", "width": round((group["left"] - cursor) / total * 100, 1), "fields": []}
				)
			end = groups[i + 1]["left"] if i + 1 < len(groups) else total
			width = max(end - group["left"], group["right"] - group["left"])
			group["right"] = group["left"] + width
			columns.append(
				{
					"label": "",
					"width": round(width / total * 100, 1),
					"fields": self.free_layout(group["items"], width, group["left"], top),
				}
			)
			cursor = group["right"]
		return columns

	def element_fields(self, element, width, ruled=True) -> list[dict]:
		if element.get("type") != "rectangle":
			node = self.node(element)
			if node and element.get("type") == "text" and not element.get("isDynamicHeight"):
				node["custom_style"] = (
					node.get("custom_style") or ""
				) + f" min-height: {round(flt(element.get('height')))}px;"
			if node and element.get("type") == "text" and not element.get("isFixedSize"):
				node["custom_style"] = (node.get("custom_style") or "") + " white-space: nowrap;"
			return [node] if node else []
		if ruled and (line := self.rule(element)):
			inner = self.element_fields(element, width, ruled=False)
			if line[0] == "top":
				return [self.divider(line[1]), *inner]
			content = max(
				(flt(c.get("startY")) + flt(c.get("height")) for c in element.get("childrens") or []),
				default=0,
			)
			divider = self.divider(line[1], flt(element.get("height")) - content)
			return [*inner, divider]
		children = element.get("childrens") or []
		if (
			element.get("layoutType") == "row"
			and len(children) > 1
			and all(c.get("type") == "rectangle" and c.get("layoutType") == "column" for c in children)
		):
			return [self.side_by_side(children)]
		if element.get("layoutType") != "column" and children:
			return self.free_layout(children, flt(element.get("width")) or width)
		return self.free_layout(children, width)

	def free_layout(self, elements, width, offset=0, top=0) -> list[dict]:
		"""Elements placed freely inside a box: a band holding several of them side by
		side becomes one flex row, a band holding one keeps its own block."""
		fields, bottom = [], top
		width = width or self.content_width()
		for band in self.rows(sorted(elements, key=lambda e: (flt(e.get("startY")), flt(e.get("startX"))))):
			top = min(flt(e.get("startY")) for e in band)
			if len(band) == 1:
				produced = self.element_fields(band[0], width)
				indent = (flt(band[0].get("startX")) - offset) / width * 100
				if produced and indent > 3:
					produced[0]["custom_style"] = f"margin-left: {round(indent, 1)}%; " + (
						produced[0].get("custom_style") or ""
					)
				spare = (
					(offset + width - flt(band[0].get("startX")) - flt(band[0].get("width"))) / width * 100
				)
				if (
					produced
					and spare > 1
					and (band[0].get("type") == "table" or produced[0].get("align") in ("right", "center"))
				):
					produced[0]["custom_style"] = f"margin-right: {round(spare, 1)}%; " + (
						produced[0].get("custom_style") or ""
					)
			else:
				parts, cursor = [], offset
				ordered = sorted(band, key=lambda e: flt(e.get("startX")))
				for element in ordered:
					left = flt(element.get("startX"))
					share = round(flt(element.get("width")), 1)
					gap = round(max(left - cursor, 0), 1)
					inner = "".join(self.element_html(e) for e in self.flatten([element]))
					parts.append(
						f'<div style="flex: 0 0 {share}px; min-width: 0; margin-left: {gap}px; '
						f'padding-top: {round(flt(element.get("startY")) - top)}px;">{inner}</div>'
					)
					cursor = left + flt(element.get("width"))
				fixed = [
					flt(e.get("startY")) - top + flt(e.get("height"))
					for e in band
					if e.get("type") in ("text", "rectangle") and not e.get("isDynamicHeight")
				]
				row_style = (
					f"display: flex; min-height: {round(max(fixed))}px;" if fixed else "display: flex;"
				)
				produced = [self.html_node(f'<div style="{row_style}">' + "".join(parts) + "</div>")]
			if produced:
				add_gap(produced[0], top - bottom)
				fields.extend(produced)
			bottom = max(flt(e.get("startY")) + flt(e.get("height")) for e in band)
		return fields

	def printed(self, elements: list[dict]) -> list[dict]:
		"""Print Designer clips a column with no width, so nothing in it ever printed."""
		hidden = [e for e in elements if e.get("layoutType") == "column" and flt(e.get("width")) < 1]
		note = _("A column with no width was left out, as Print Designer did not print it.")
		if any(e.get("childrens") for e in hidden) and note not in self.notes:
			self.notes.append(note)
		return [e for e in elements if e not in hidden]

	def side_by_side(self, columns) -> dict:
		parts, fixed = [], []
		for column in sorted(self.printed(columns), key=lambda c: flt(c.get("startX"))):
			children = column.get("childrens") or []
			inner, cursor = "", 0
			for child in sorted(children, key=lambda e: (flt(e.get("startY")), flt(e.get("startX")))):
				html = "".join(self.element_html(e) for e in self.flatten([child]))
				gap, indent = (
					round(max(flt(child.get("startY")) - cursor, 0)),
					round(flt(child.get("startX"))),
				)
				style = (f"margin-top: {gap}px; " if gap else "") + (
					f"margin-left: {indent}px;" if indent else ""
				)
				inner += f'<div style="{style.strip()}">{html}</div>' if style else html
				cursor = max(cursor, flt(child.get("startY")) + flt(child.get("height")))
			parts.append(
				f'<div style="flex: {round(flt(column.get("width")))} 1 0; min-width: 0; overflow-wrap: anywhere;">{inner}</div>'
			)
			fixed += [
				flt(c.get("startY")) + flt(c.get("height"))
				for c in children
				if c.get("type") in ("text", "rectangle") and not c.get("isDynamicHeight")
			]
		row_style = f"display: flex; min-height: {round(max(fixed))}px;" if fixed else "display: flex;"
		return self.html_node(f'<div style="{row_style}">' + "".join(parts) + "</div>")

	def flatten(self, elements) -> list[dict]:
		flat = []
		for element in sorted(elements, key=lambda e: (flt(e.get("startY")), flt(e.get("startX")))):
			if element.get("type") == "rectangle":
				inner = self.flatten(element.get("childrens") or [])
				if line := self.rule(element):
					mark = {"type": "line", "color": line[1]}
					inner = [mark, *inner] if line[0] == "top" else [*inner, mark]
				flat.extend(inner)
			else:
				flat.append(element)
		return flat

	# ----- elements -------------------------------------------------------------

	def node(self, element) -> dict | None:
		kind = element.get("type")
		if kind == "table":
			return self.table_node(element)
		if kind == "image":
			return self.image_node(element)
		if kind == "barcode":
			return self.barcode_node(element)
		if kind == "text":
			if element.get("isDynamic"):
				if field := self.field_node(element):
					return field
			elif not JINJA.search(element.get("content") or "") and not re.search(
				r"<(?!br|b>|/b>|span|/span)", element.get("content") or ""
			):
				return self.static_text_node(element)
			return self.html_node(self.element_html(element))
		self.notes.append(_("A {0} element was left out.").format(kind))
		return None

	def name(self, prefix) -> str:
		self.counter += 1
		return f"{prefix}_{self.counter}"

	def html_node(self, html) -> dict:
		return {
			"label": "Custom HTML",
			"fieldname": self.name("custom_html"),
			"fieldtype": "HTML",
			"html": html,
			"custom": 1,
		}

	def static_text_node(self, element) -> dict | None:
		text = re.sub(r"<br\s*/?>", "\n", element.get("content") or "")
		text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ").strip()
		if not text:
			return None
		node = {
			"label": "Text",
			"fieldname": self.name("static_text"),
			"fieldtype": "Static Text",
			"text": text,
			"custom": 1,
		}
		node.update(self.style_props(self.styled(element)))
		return node

	def field_node(self, element) -> dict | None:
		items = [
			i
			for i in element.get("dynamicContent") or []
			if not (i.get("is_static") and not (i.get("value") or "").strip())
		]
		if len(items) != 1:
			return None
		item = items[0]
		if (
			item.get("is_static")
			or item.get("parentField")
			or item.get("tableName")
			or item.get("fieldname") in PAGE_NUMBER_FIELDS
		):
			return None
		df = self.meta.get_field(item.get("fieldname")) if item.get("fieldname") not in ("name",) else None
		if item.get("fieldname") != "name" and not df:
			return None
		node = {
			"label": html.unescape(item.get("label") or (df.label if df else _("Name")))
			.strip()
			.rstrip(":")
			.strip(),
			"fieldname": item["fieldname"],
			"fieldtype": df.fieldtype if df else "Data",
		}
		if df and df.options:
			node["options"] = df.options
		node["show_label"] = "inline" if item.get("is_labelled") else "hide"
		node.update(self.style_props({**self.styled(element), **(item.get("style") or {})}))
		return node

	def table_node(self, element) -> dict | None:
		table = element.get("table") or {}
		if not table.get("fieldname"):
			self.notes.append(_("A table with no child table selected was left out."))
			return None
		columns = []
		for column in element.get("columns") or []:
			fields = [
				d for d in column.get("dynamicContent") or [] if d.get("fieldname") and not d.get("is_static")
			]
			if not fields:
				self.notes.append(
					_("Table column {0} has no field and was left out.").format(column.get("label") or "")
				)
				continue
			first = fields[0]
			col = {
				"label": html.unescape(column.get("label") or first.get("label") or ""),
				"fieldname": first["fieldname"],
				"fieldtype": first.get("fieldtype") or "Data",
				"width": round(flt(column.get("width")), 1),
			}
			if len(fields) > 1:
				col["merged_fields"] = [
					{
						"fieldname": f["fieldname"],
						"fieldtype": f.get("fieldtype") or "Data",
						"style": "secondary",
					}
					for f in fields[1:]
				]
			columns.append(col)
		unsized = [col for col in columns if not col["width"]]
		if unsized:
			rest = max(100 - sum(col["width"] for col in columns), 5 * len(unsized))
			for col in unsized:
				col["width"] = round(rest / len(unsized), 1)
		style = self.styled(element)
		header = self.styled(element, "headerStyle")
		bordered = (
			flt(re.sub(r"[^\d.]", "", str(style.get("borderWidth") or "0")) or 0) > 0
			and style.get("borderStyle") not in ("none", "hidden")
			and not is_white(style.get("borderColor"))
		)
		node = {
			"label": "",
			"fieldname": table.get("fieldname"),
			"fieldtype": "Table",
			"options": table.get("options"),
			"table_columns": columns,
			"show_label": "hide",
			"table_style": "lined",
			"table_bordered": bordered,
			"table_radius": 0,
		}
		height_type = element.get("heightType") or ("auto" if element.get("isDynamicHeight") else "fixed")
		if not bordered and height_type != "auto" and flt(element.get("height")):
			node["table_min_height"] = round(flt(element.get("height")))
		if (padding := style.get("paddingTop")) is not None:
			node["table_cell_padding"] = round(flt(re.sub(r"[^\d.]", "", str(padding)) or 0))
		text = {
			k: v
			for k, v in style.items()
			if k in ("fontSize", "fontFamily", "color", "lineHeight", "letterSpacing")
		}
		if style.get("textAlign") in ("center", "right"):
			text["textAlign"] = style["textAlign"]
		if size := flt(re.sub(r"[^\d.]", "", str(text.get("fontSize") or "")) or 0):
			text["fontSize"] = f"{round(size / TABLE_TEXT_SCALE, 2)}px"
		if text:
			node["custom_style"] = css(text)
		if flt(re.sub(r"[^\d.]", "", str(header.get("fontSize") or "")) or 99) <= 2 or is_white(
			header.get("color")
		):
			node["table_header"] = "none"
		elif is_white(header.get("backgroundColor")):
			node["table_header"] = "plain"
		elif header.get("backgroundColor"):
			node["table_header_bg"] = header["backgroundColor"]
		if (color := style.get("borderColor") or header.get("borderColor")) and not is_white(color):
			node["table_border_color"] = color
		return node

	def image_node(self, element) -> dict | None:
		image = element.get("image") or {}
		if element.get("isDynamic") and image.get("fieldname"):
			if image.get("parentField") and image.get("doctype"):
				return self.html_node(
					f"{{%- set image_url = frappe.db.get_value({image.get('doctype')!r}, doc.{image['parentField']}, {image['fieldname']!r}) -%}}"
					"{%- if image_url -%}"
					f'<img src="{{{{ image_url }}}}" style="width: {round(flt(element.get("width")) / PX_PER_MM, 1)}mm; max-width: 100%;">'
					"{%- endif -%}"
				)
			return {
				"label": image.get("label") or "",
				"fieldname": image["fieldname"],
				"fieldtype": "Attach Image",
				"show_label": "hide",
				"width": f"{round(flt(element.get('width')) / PX_PER_MM, 1)}mm",
			}
		url = image.get("file_url")
		if not url:
			return None
		return {
			"label": "Image",
			"fieldname": self.name("image"),
			"fieldtype": "Image",
			"image_url": url,
			"width": f"{round(flt(element.get('width')) / PX_PER_MM, 1)}mm",
			"custom": 1,
		}

	def barcode_node(self, element) -> dict | None:
		value = (element.get("value") or "").strip()
		barcode_format = (element.get("barcodeFormat") or "").lower()
		kind = BARCODE_FORMATS.get(barcode_format, "CODE128")
		size = f"{round(flt(element.get('width')) / PX_PER_MM, 1)}mm"
		field = re.fullmatch(r"{{\s*doc\.(\w+)\s*}}", value)
		known_field = bool(field and (field.group(1) == "name" or self.meta.get_field(field.group(1))))
		if (
			barcode_format
			and barcode_format not in BARCODE_FORMATS
			and (known_field or not JINJA.search(value))
		):
			self.notes.append(
				_("The {0} barcode type was changed to CODE128.").format(barcode_format.upper())
			)
		if known_field:
			return {
				"label": "Barcode",
				"fieldname": self.name("barcode"),
				"fieldtype": "Barcode",
				"barcode_format": kind,
				"barcode_field": field.group(1),
				"width": size,
				"custom": 1,
			}
		if not JINJA.search(value):
			return {
				"label": "Barcode",
				"fieldname": self.name("barcode"),
				"fieldtype": "Barcode",
				"barcode_format": kind,
				"barcode_value": value,
				"width": size,
				"custom": 1,
			}
		if kind != "QR":
			self.notes.append(_("A barcode built with Jinja was left out; add it again in the editor."))
			return None
		return self.html_node(
			"{%- set qr_value -%}" + value + "{%- endset -%}"
			"{%- set qr_code = get_qr_code(qr_value | trim) if qr_value | trim -%}"
			"{%- if qr_code -%}"
			f'<img src="{{{{ qr_code }}}}" style="width: {size};">'
			"{%- endif -%}"
		)

	# ----- html -----------------------------------------------------------------

	def element_html(self, element) -> str:
		if element.get("type") == "line":
			return f'<div style="border-top: 1px solid {element["color"]};"></div>'
		style = css(self.styled(element))
		if element.get("type") == "text" and not element.get("isFixedSize"):
			style = f"{style} white-space: nowrap;".strip()
		if element.get("type") == "text" and element.get("isDynamic"):
			inner = "".join(self.dynamic_part(item) for item in element.get("dynamicContent") or [])
		elif element.get("type") == "text":
			inner = element.get("content") or ""
		else:
			node = self.node(element)
			if not node:
				return ""
			if node["fieldtype"] == "HTML":
				return node["html"]
			if node["fieldtype"] == "Image":
				return f'<img src="{escape_html(node["image_url"])}" style="width: {node["width"]}; max-width: 100%;">'
			if node["fieldtype"] == "Attach Image":
				return f'{{%- if doc.{node["fieldname"]} -%}}<img src="{{{{ doc.{node["fieldname"]} }}}}" style="width: {node["width"]}; max-width: 100%;">{{%- endif -%}}'
			if node["fieldtype"] == "Table":
				return self.table_html(element, node)
			if node["fieldtype"] == "Barcode":
				value = (
					f"doc.get({node['barcode_field']!r})"
					if node.get("barcode_field")
					else repr(node["barcode_value"])
				)
				return (
					f"{{%- set barcode_value = ({value} or '') | string -%}}"
					f"{{%- set barcode = get_barcode(barcode_value, {node['barcode_format']!r}) if barcode_value -%}}"
					f'{{%- if barcode -%}}<img src="{{{{ barcode }}}}" style="width: {node["width"]}; max-width: 100%;">{{%- endif -%}}'
				)
			if node["fieldtype"] != "Static Text":
				return f"{{{{ doc.get_formatted({node['fieldname']!r}) }}}}"
			inner = node.get("text") or ""
		return f'<div style="{style}">{inner}</div>' if style else f"<div>{inner}</div>"

	def table_html(self, element, node) -> str:
		cell = css(self.styled(element))
		header = (
			""
			if node.get("table_header") == "none"
			else "<tr>"
			+ "".join(
				f'<th width="{c["width"]}%" style="{css(self.styled(element, "headerStyle"))}">{escape_html(c["label"])}</th>'
				for c in node["table_columns"]
			)
			+ "</tr>"
		)
		cells = "".join(
			f'<td width="{c["width"]}%" style="{cell}">{{{{ row.get_formatted({c["fieldname"]!r}, doc) }}}}</td>'
			for c in node["table_columns"]
		)
		return (
			'<table style="width: 100%; border-collapse: collapse;">'
			f"{header}{{%- for row in doc.{node['fieldname']} -%}}<tr>{cells}</tr>{{%- endfor -%}}</table>"
		)

	def dynamic_part(self, item) -> str:
		style = css(item.get("style") or {})
		fieldname = item.get("fieldname") or ""
		if item.get("is_static"):
			value = item.get("value") or ""
		elif fieldname in PAGE_NUMBER_FIELDS:
			value = PAGE_NUMBER_FIELDS[fieldname]
		elif item.get("parentField"):
			value = (
				f"{{{{ frappe.format(frappe.db.get_value({item.get('doctype')!r}, doc.{item['parentField']}, {fieldname!r}), {item.get('fieldtype')!r}) or '' }}}}"
				if item.get("doctype")
				else f"{{{{ doc.get_formatted({fieldname!r}) }}}}"
			)
		else:
			value = f"{{{{ doc.get_formatted({fieldname!r}) }}}}"
		if item.get("is_labelled") and item.get("label"):
			base = (self.global_styles.get("dynamicText") or {}).get("labelStyle") or {}
			label_style = css({**base, **(item.get("labelStyle") or {})})
			value = f'<span style="{label_style}">{escape_html(html.unescape(item["label"]))}</span> {value}'
		if style:
			value = f'<span style="{style}">{value}</span>'
		return value + ("<br>" if item.get("nextLine") else "")

	def style_props(self, style) -> dict:
		props = {}
		if align := style.get("textAlign"):
			if align in ("left", "center", "right"):
				props["align"] = align
		rest = {k: v for k, v in style.items() if k != "textAlign"}
		if custom := css(rest):
			props["custom_style"] = custom
		return props


def tile_columns(section, total):
	columns = section["columns"]
	if len(columns) < 2:
		return
	section["gap"] = 0
	last = len(columns) - 1
	for i, column in enumerate(columns):
		pad_left = COLUMN_PADDING if i > 0 else 0
		pad_right = COLUMN_PADDING if i < last else 0
		outer = flt(column.get("width")) / 100 * total
		column["width"] = round(max(outer - pad_left - pad_right, 1) / total * 100, 2)
		for field in column["fields"]:
			style = (field.get("custom_style") or "").strip()
			margin = {"left": -pad_left, "right": -pad_right}
			for side, value in SIDE_MARGIN.findall(style):
				margin[side] += flt(value) / 100 * outer
			style = SIDE_MARGIN.sub("", style).strip()
			if style and not style.endswith(";"):
				style += ";"
			margins = f"margin-inline-start: {round(margin['left'], 1)}px; margin-inline-end: {round(margin['right'], 1)}px;"
			field["custom_style"] = f"{style} {margins}".strip()


def add_gap(node, gap):
	if gap > 3:
		style = node.get("custom_style") or ""
		shorthand = re.compile(r"(^|;)(\s*margin\s*:\s*)(\d+(?:\.\d+)?)px")
		if shorthand.search(style):
			node["custom_style"] = shorthand.sub(
				lambda m: f"{m[1]}{m[2]}{round(flt(m[3]) + gap)}px", style, count=1
			)
		else:
			node["custom_style"] = f"margin-top: {round(gap)}px; " + style


def is_white(color) -> bool:
	return (color or "").strip().lower() in ("#fff", "#ffffff", "white", "rgb(255, 255, 255)")


def css(style: dict) -> str:
	parts = []
	draws_border = flt(re.sub(r"[^\d.]", "", str(style.get("borderWidth") or "0")) or 0) > 0 and style.get(
		"borderStyle"
	) not in ("none", "hidden")
	for key, value in style.items():
		if key == "backgroundColor" and is_white(value):
			continue
		if key.startswith("border") and not draws_border:
			continue
		prop = CSS_PROPERTIES.get(key)
		if prop and value not in (None, ""):
			parts.append(f"{prop}: {value};")
	return " ".join(parts)
