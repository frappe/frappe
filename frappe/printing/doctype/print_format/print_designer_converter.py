# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt

PX_PER_MM = 96 / 25.4
TABLE_TEXT_SCALE = 0.9
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


def is_print_designer_format(doc) -> bool:
	return bool(
		doc.get("print_designer")
		and (doc.get("print_designer_print_format") or doc.get("print_designer_body"))
	)


def convert_print_designer_format(doc) -> tuple[dict, list[str]]:
	"""Return a print format editor layout for a Print Designer format, and notes on
	what could not be carried over exactly."""
	return PrintDesignerConverter(doc).convert()


@frappe.whitelist()
def create_editor_format(print_format: str, name: str | None = None) -> str:
	"""Save a converted copy of a Print Designer format as a new editor format."""
	frappe.only_for("System Manager")
	source = frappe.get_doc("Print Format", print_format)
	if not is_print_designer_format(source):
		frappe.throw(_("{0} is not a Print Designer format.").format(frappe.bold(print_format)))
	layout, notes = convert_print_designer_format(source)
	target = frappe.new_doc("Print Format")
	target.__newname = name or _("{0} (Editor)").format(source.name)
	target.update(
		{
			"doc_type": source.doc_type,
			"module": source.module,
			"standard": "No",
			"print_format_builder_beta": 1,
			"format_data": json.dumps(layout),
			"default_print_language": source.default_print_language,
			"pdf_generator": "chrome",
			"page_number": source.page_number,
			"font": converted_font(source),
			**converted_margins(source),
		}
	)
	target.insert()
	if notes:
		target.add_comment("Comment", "<br>".join(escape_html(n) for n in notes))
	return target.name


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
			header = load_json(self.doc.get("print_designer_header")) or []
			body = ((load_json(self.doc.get("print_designer_body")) or [{}])[0] or {}).get("childrens") or []
			footer = load_json(self.doc.get("print_designer_footer")) or []
			self.notes.append(_("No row and column layout was saved, so rows were grouped by position."))

		layout = {
			"header": self.zone(header, flt(self.page.get("headerHeight"))),
			"sections": self.sections(body),
			"footer": self.zone(footer, flt(self.page.get("footerHeight"))),
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
		size = (self.settings.get("currentPageSize") or "").upper()
		if size in ("A4", "A5", "A3"):
			page["size"] = size
		elif size in ("LETTER", "LEGAL", "TABLOID"):
			page["size"] = size.title()
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
		if element.get("type") != "rectangle" or element.get("layoutType"):
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
		sections = self.sections(elements)
		if len(sections) == 1:
			columns = sections[0]["columns"]
		elif all(len(s["columns"]) == 1 for s in sections):
			columns = [{"label": "", "fields": [f for s in sections for f in s["columns"][0]["fields"]]}]
		else:
			rows = self.rows(sorted(elements, key=lambda e: (flt(e.get("startY")), flt(e.get("startX")))))
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
		return {"columns": columns}

	def row_html(self, row) -> str:
		total = self.content_width()
		compiled = len(row) == 1 and row[0].get("layoutType") == "row"
		children = row[0].get("childrens") or [] if compiled else row
		top = 0 if compiled else min(flt(e.get("startY")) for e in row)
		height = (
			flt(row[0].get("height"))
			if compiled
			else max(flt(e.get("startY")) + flt(e.get("height")) for e in row) - top
		)
		parts = []
		for child in sorted(children, key=lambda c: flt(c.get("startX"))):
			inner = "".join(self.element_html(e) for e in self.flatten([child]))
			nested = child.get("childrens") if child.get("layoutType") == "column" else None
			offset = min(flt(c.get("startY")) for c in nested) if nested else flt(child.get("startY")) - top
			parts.append(
				f'<div style="flex: 0 1 {round(flt(child.get("width")) / total * 100, 1)}%; min-width: 0; '
				f'overflow-wrap: anywhere; padding-top: {round(max(offset, 0))}px;">{inner}</div>'
			)
		return (
			f'<div style="display: flex; justify-content: space-between; min-height: {round(height)}px;">'
			+ "".join(parts)
			+ "</div>"
		)

	def sections(self, elements) -> list[dict]:
		elements = sorted(elements or [], key=lambda e: (flt(e.get("startY")), flt(e.get("startX"))))
		sections, previous_bottom = [], 0
		for row in self.rows(elements):
			top = min(flt(e.get("startY")) for e in row)
			section = {"label": "", "columns": self.columns(row)}
			gap = top - previous_bottom
			if sections and gap > 4:
				section["margin"] = {"top": round(gap), "right": 0, "bottom": 0, "left": 0}
			if any(c["fields"] for c in section["columns"]):
				sections.append(section)
			previous_bottom = max(flt(e.get("startY")) + flt(e.get("height")) for e in row)
		return sections

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

	def columns(self, row) -> list[dict]:
		total = self.content_width()
		if len(row) == 1 and row[0].get("layoutType") == "row":
			children = row[0].get("childrens") or []
			if children and all(c.get("layoutType") == "column" for c in children):
				return [
					{
						"label": "",
						"width": round(flt(c.get("width")) / total * 100, 1),
						"fields": self.free_layout(c.get("childrens") or [], flt(c.get("width"))),
					}
					for c in sorted(children, key=lambda c: flt(c.get("startX")))
				]
			row = children
		if any(flt(e.get("width")) > 0.6 * total for e in row) and len(row) > 1:
			return [{"label": "", "fields": self.free_layout(row, total)}]
		return self.columns_by_position(row, total)

	def columns_by_position(self, elements, total) -> list[dict]:
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
					"fields": self.free_layout(group["items"], width, group["left"]),
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
			and all(c.get("layoutType") == "column" for c in children)
		):
			return [self.side_by_side(children)]
		if element.get("layoutType") != "column" and children:
			return self.free_layout(children, flt(element.get("width")) or width)
		return self.free_layout(children, width)

	def free_layout(self, elements, width, offset=0) -> list[dict]:
		"""Elements placed freely inside a box: a band holding several of them side by
		side becomes one flex row, a band holding one keeps its own block."""
		fields, bottom = [], 0
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
				produced = [self.html_node('<div style="display: flex;">' + "".join(parts) + "</div>")]
			if produced:
				add_gap(produced[0], top - bottom)
				fields.extend(produced)
			bottom = max(flt(e.get("startY")) + flt(e.get("height")) for e in band)
		return fields

	def side_by_side(self, columns) -> dict:
		parts = []
		for column in sorted(columns, key=lambda c: flt(c.get("startX"))):
			inner = "".join(self.element_html(e) for e in self.flatten(column.get("childrens") or []))
			parts.append(
				f'<div style="flex: {round(flt(column.get("width")))} 1 0; min-width: 0; overflow-wrap: anywhere;">{inner}</div>'
			)
		return self.html_node('<div style="display: flex;">' + "".join(parts) + "</div>")

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
		text = re.sub(r"<[^>]+>", "", text).replace("&nbsp;", " ").strip()
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
			"label": (item.get("label") or (df.label if df else _("Name"))).strip().rstrip(":").strip(),
			"fieldname": item["fieldname"],
			"fieldtype": df.fieldtype if df else "Data",
		}
		if df and df.options:
			node["options"] = df.options
		node["show_label"] = "inline" if item.get("is_labelled") else "hide"
		node.update(self.style_props({**self.styled(element), **(item.get("style") or {})}))
		return node

	def table_node(self, element) -> dict:
		table = element.get("table") or {}
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
				"label": column.get("label") or first.get("label") or "",
				"fieldname": first["fieldname"],
				"fieldtype": first.get("fieldtype") or "Data",
				"width": round(flt(column.get("width")) or 10, 1),
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
			"table_style": "grid" if bordered else "lined",
			"table_bordered": bordered,
			"table_radius": 0,
		}
		if not bordered and flt(element.get("height")):
			node["table_min_height"] = round(flt(element.get("height")))
		if (padding := style.get("paddingTop")) is not None:
			node["table_cell_padding"] = round(flt(re.sub(r"[^\d.]", "", str(padding)) or 0))
		text = {
			k: v
			for k, v in style.items()
			if k in ("fontSize", "fontFamily", "color", "lineHeight", "letterSpacing")
		}
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
			return {
				"label": image.get("label") or "",
				"fieldname": image["fieldname"],
				"fieldtype": "Attach Image",
				"show_label": "hide",
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
		kind = "QR" if (element.get("barcodeFormat") or "").lower() in ("qrcode", "qr") else "CODE128"
		size = f"{round(flt(element.get('width')) / PX_PER_MM, 1)}mm"
		field = re.fullmatch(r"{{\s*doc\.(\w+)\s*}}", value)
		if field and self.meta.get_field(field.group(1)):
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
			"{%- if qr_value | trim and get_qr_code is defined -%}"
			f'<img src="data:image/png;base64,{{{{ get_qr_code(qr_value | trim) }}}}" style="width: {size};">'
			"{%- endif -%}"
		)

	# ----- html -----------------------------------------------------------------

	def element_html(self, element) -> str:
		if element.get("type") == "line":
			return f'<div style="border-top: 1px solid {element["color"]};"></div>'
		style = css(self.styled(element))
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
				return f'{{%- if doc.{node["fieldname"]} -%}}<img src="{{{{ doc.{node["fieldname"]} }}}}" style="max-width: 100%;">{{%- endif -%}}'
			if node["fieldtype"] == "Table":
				return self.table_html(element, node)
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
				f'<th style="{css(self.styled(element, "headerStyle"))}">{escape_html(c["label"])}</th>'
				for c in node["table_columns"]
			)
			+ "</tr>"
		)
		cells = "".join(
			f'<td style="{cell}">{{{{ row.get_formatted({c["fieldname"]!r}, doc) }}}}</td>'
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
				f"{{{{ frappe.db.get_value({item.get('doctype')!r}, doc.{item['parentField']}, {fieldname!r}) or '' }}}}"
				if item.get("doctype")
				else f"{{{{ doc.get_formatted({fieldname!r}) }}}}"
			)
		else:
			value = f"{{{{ doc.get_formatted({fieldname!r}) }}}}"
		if item.get("is_labelled") and item.get("label"):
			base = (self.global_styles.get("dynamicText") or {}).get("labelStyle") or {}
			label_style = css({**base, **(item.get("labelStyle") or {})})
			value = f'<span style="{label_style}">{escape_html(item["label"])}</span> {value}'
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


def add_gap(node, gap):
	if gap > 3:
		node["custom_style"] = f"margin-top: {round(gap)}px; " + (node.get("custom_style") or "")


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
