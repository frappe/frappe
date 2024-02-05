# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

# import frappe
from frappe.model.document import Document


class WebPageBlock(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		add_background_image: DF.Check
		add_border_at_bottom: DF.Check
		add_border_at_top: DF.Check
		add_bottom_padding: DF.Check
		add_container: DF.Check
		add_shade: DF.Check
		add_top_padding: DF.Check
		background_image: DF.AttachImage | None
		css_class: DF.SmallText | None
		hide_block: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		section_id: DF.Data | None
		web_template: DF.Link | None
		web_template_values: DF.Code | None
	# end: auto-generated types

	pass
