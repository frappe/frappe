# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from xml.etree import ElementTree

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.html_utils import sanitize_svg


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
		self.svg = sanitize_svg(self.svg or "").strip()
		if not is_single_svg(self.svg):
			frappe.throw(_("Content must be a single <svg> element"))


def is_single_svg(svg: str) -> bool:
	"""True only when `svg` parses as a lone root element and that element is <svg>."""
	try:
		root = ElementTree.fromstring(svg)
	except ElementTree.ParseError:
		return False
	return root.tag.rsplit("}", 1)[-1] == "svg"
