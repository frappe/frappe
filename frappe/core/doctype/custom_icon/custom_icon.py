# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import re
from xml.etree import ElementTree

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.html_utils import sanitize_svg

SYMBOL_CACHE_KEY = "custom_icon_symbols"
DROPPED_ATTRIBUTES = ("id", "width", "height")
ICON_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


class CustomIcon(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		icon_name: DF.Data
		svg: DF.Code
	# end: auto-generated types

	def validate(self):
		# the name becomes a DOM id and reaches markup templates unescaped, so keep it inert
		if not ICON_NAME.match(self.icon_name or ""):
			frappe.throw(_("Icon Name can only contain letters, numbers, hyphens and underscores"))

		self.svg = sanitize_svg(self.svg or "").strip()
		if not is_single_svg(self.svg):
			frappe.throw(_("Content must be a single <svg> element"))

	def on_update(self):
		clear_symbol_cache()

	def on_trash(self):
		clear_symbol_cache()


def is_single_svg(svg: str) -> bool:
	"""True only when `svg` parses as a lone root element and that element is <svg>."""
	try:
		root = ElementTree.fromstring(svg)
	except ElementTree.ParseError:
		return False
	return root.tag.rsplit("}", 1)[-1] == "svg"


def get_symbols() -> list[dict]:
	"""Every Custom Icon as `<symbol>` markup the desk sprite can resolve through `<use>`."""
	return frappe.cache.get_value(
		SYMBOL_CACHE_KEY,
		lambda: [
			{"name": icon.icon_name, "symbol": to_symbol(icon.icon_name, icon.svg)}
			for icon in frappe.get_all("Custom Icon", fields=["icon_name", "svg"], order_by="icon_name")
		],
	)


def clear_symbol_cache() -> None:
	frappe.cache.delete_value(SYMBOL_CACHE_KEY)
	# boot is cached per user and now carries a stale icon set
	frappe.clear_cache()


def to_symbol(icon_name: str, svg: str) -> str:
	"""Rewrite a standalone `<svg>` as a `<symbol id="icon-{icon_name}">`.

	Presentation attributes stay on the symbol: lucide-style icons carry `stroke`
	and `fill` on the root element and render blank without them. Width and height
	are dropped so the sizing classes on `<use>` win.
	"""
	root = ElementTree.fromstring(svg)
	symbol = ElementTree.Element("symbol")
	symbol.attrib = {key: value for key, value in root.attrib.items() if key not in DROPPED_ATTRIBUTES}
	symbol.set("id", f"icon-{icon_name}")
	if "stroke" not in symbol.attrib:
		# an SVG that names no stroke has none, but the desk icon styles would inherit one in
		symbol.set("stroke", "none")
	symbol.text = root.text
	symbol.extend(list(root))
	strip_namespaces(symbol)

	return ElementTree.tostring(symbol, encoding="unicode")


def strip_namespaces(element: ElementTree.Element) -> None:
	"""Drop `{http://www.w3.org/2000/svg}` tag prefixes, which serialize back as `ns0:` noise.

	The sprite wrapper the desk injects these into already declares the SVG namespace.
	"""
	for node in element.iter():
		if isinstance(node.tag, str):
			node.tag = node.tag.rsplit("}", 1)[-1]
