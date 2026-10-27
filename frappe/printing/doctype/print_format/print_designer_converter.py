# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt

PX_PER_MM = 96 / 25.4
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
			"header": self.zone(header),
			"sections": self.sections(body),
			"footer": self.zone(footer),
		}
		if setup := (self.settings.get("userProvidedJinja") or "").strip():
			layout["jinja_setup"] = setup
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
		size = (self.settings.get("currentPageSize") or "").upper()
		sizes = {"A4", "A5", "A3", "LETTER", "LEGAL", "TABLOID"}
		if size in sizes:
			return {"size": size.title() if size not in ("A4", "A5", "A3") else size}
		width, height = flt(self.page.get("width")), flt(self.page.get("height"))
		if width and height and width > height:
			return {"orientation": "Landscape"}
		return None

	def content_width(self) -> float:
		width = flt(self.page.get("width")) or 793.7
		return max(width - flt(self.page.get("marginLeft")) - flt(self.page.get("marginRight")), 1)

	# ----- structure ------------------------------------------------------------

	def zone(self, elements) -> dict:
		sections = self.sections(elements)
		if len(sections) == 1:
			return {"columns": sections[0]["columns"]}
		if all(len(s["columns"]) == 1 for s in sections):
			return {
				"columns": [{"label": "", "fields": [f for s in sections for f in s["columns"][0]["fields"]]}]
			}
		rows = self.rows(sorted(elements, key=lambda e: (flt(e.get("startY")), flt(e.get("startX")))))
		html = "".join(self.row_html(row) for row in rows)
		return {"columns": [{"label": "", "fields": [self.html_node(html)]}]}

	def row_html(self, row) -> str:
		total = self.content_width()
		children = (
			row[0].get("childrens") or [] if len(row) == 1 and row[0].get("layoutType") == "row" else row
		)
		parts = []
		for child in sorted(children, key=lambda c: flt(c.get("startX"))):
			inner = "".join(self.element_html(e) for e in self.flatten([child]))
			parts.append(
				f'<div style="flex: 0 1 {round(flt(child.get("width")) / total * 100, 1)}%; min-width: 0; overflow-wrap: anywhere;">{inner}</div>'
			)
		return (
			'<div style="display: flex; justify-content: space-between; align-items: center;">'
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
						"fields": self.stack(c.get("childrens") or [], flt(c.get("width"))),
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

	def stack(self, elements, width) -> list[dict]:
		fields, bottom = [], 0
		for element in sorted(elements, key=lambda e: (flt(e.get("startY")), flt(e.get("startX")))):
			produced = self.element_fields(element, width)
			if produced:
				add_gap(produced[0], flt(element.get("startY")) - bottom)
				fields.extend(produced)
			bottom = flt(element.get("startY")) + flt(element.get("height"))
		return fields

	def element_fields(self, element, width) -> list[dict]:
		if element.get("type") != "rectangle":
			node = self.node(element)
			return [node] if node else []
		children = element.get("childrens") or []
		if (
			element.get("layoutType") == "row"
			and len(children) > 1
			and all(c.get("layoutType") == "column" for c in children)
		):
			return [self.side_by_side(children)]
		if element.get("layoutType") != "column" and children:
			return self.free_layout(children, flt(element.get("width")) or width)
		return self.stack(children, width)

	def free_layout(self, elements, width, offset=0) -> list[dict]:
		"""Elements placed freely inside a box: a band holding several of them side by
		side becomes one flex row, a band holding one keeps its own block."""
		fields, bottom = [], 0
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
				for i, element in enumerate(ordered):
					left = flt(element.get("startX"))
					end = flt(ordered[i + 1].get("startX")) if i + 1 < len(ordered) else offset + width
					share = round(max(end - left, flt(element.get("width"))) / width * 100, 1)
					gap = round(max(left - cursor, 0) / width * 100, 1)
					inner = "".join(self.element_html(e) for e in self.flatten([element]))
					parts.append(
						f'<div style="flex: 0 1 {share}%; min-width: 0; overflow-wrap: anywhere; margin-left: {gap}%; '
						f'padding-top: {round(flt(element.get("startY")) - top)}px;">{inner}</div>'
					)
					cursor = left + max(end - left, flt(element.get("width")))
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
				flat.extend(self.flatten(element.get("childrens") or []))
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
			"fieldtype": "StaticText",
			"text": text,
			"custom": 1,
		}
		node.update(self.style_props(element.get("style") or {}))
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
		node.update(self.style_props({**(element.get("style") or {}), **(item.get("style") or {})}))
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
		style = element.get("style") or {}
		header = element.get("headerStyle") or {}
		node = {
			"label": "",
			"fieldname": table.get("fieldname"),
			"fieldtype": "Table",
			"options": table.get("options"),
			"table_columns": columns,
			"show_label": "hide",
			"table_bordered": cint(re.sub(r"[^\d]", "", str(style.get("borderWidth") or "0")) or 0) > 0
			and not is_white(style.get("borderColor")),
		}
		if flt(re.sub(r"[^\d.]", "", str(header.get("fontSize") or "")) or 99) <= 2 or is_white(
			header.get("color")
		):
			node["table_header"] = "none"
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
		style = css(element.get("style") or {})
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
			if node["fieldtype"] not in ("StaticText",):
				return f"{{{{ doc.get_formatted({node['fieldname']!r}) }}}}"
			inner = node.get("text") or ""
		return f'<div style="{style}">{inner}</div>' if style else f"<div>{inner}</div>"

	def table_html(self, element, node) -> str:
		cell = css(element.get("style") or {})
		header = (
			""
			if node.get("table_header") == "none"
			else "<tr>"
			+ "".join(
				f'<th style="{css(element.get("headerStyle") or {})}">{escape_html(c["label"])}</th>'
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
			label_style = css(item.get("labelStyle") or {})
			value = f'<span style="{label_style}">{escape_html(item["label"])}</span> {value}'
		if style:
			value = f'<span style="{style}">{value}</span>'
		return ("<br>" if item.get("nextLine") else "") + value

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
	for key, value in style.items():
		prop = CSS_PROPERTIES.get(key)
		if prop and value not in (None, ""):
			parts.append(f"{prop}: {value};")
	return " ".join(parts)
