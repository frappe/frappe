# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.defaults import clear_default
from frappe.model.document import Document
from frappe.utils import flt, is_image, set_default


class LetterHead(Document):
	def validate(self):
		self.set_image()
		self.use_as_default()
		if self.disabled and self.is_default:
			frappe.throw(_("Letter Head cannot be both disabled and default"))

	def on_update(self):
		if self.is_default:
			self.unset_other_defaults()
			set_default("letter_head", self.name)

		clear_default("letter_head", self.name)

	def on_trash(self):
		if self.is_default:
			frappe.throw(_("Default Letter Head cannot be deleted"))

		clear_default("letter_head", self.name)

	def use_as_default(self):
		if (
			self.is_default
			or self.disabled
			or frappe.db.exists("Letter Head", {"is_default": 1, "name": ("!=", self.name)})
		):
			return

		self.is_default = 1

	def unset_other_defaults(self):
		table = frappe.qb.DocType("Letter Head")
		frappe.qb.update(table).set(table.is_default, 0).where(table.name != self.name).run()

	def set_image(self):
		if self.source == "Image":
			self.set_image_as_html(
				field="image",
				width="image_width",
				height="image_height",
				align="align",
				html_field="content",
				dimension_prefix="image_",
				success_msg=_("Header HTML set from attachment {0}").format(self.image),
				failure_msg=_("Please attach an image file to set HTML for Letter Head."),
			)

		if self.footer_source == "Image":
			self.set_image_as_html(
				field="footer_image",
				width="footer_image_width",
				height="footer_image_height",
				align="footer_align",
				html_field="footer",
				dimension_prefix="footer_image_",
				success_msg=_("Footer HTML set from attachment {0}").format(self.footer_image),
				failure_msg=_("Please attach an image file to set HTML for Footer."),
			)

	def set_image_as_html(
		self, field, width, height, dimension_prefix, align, html_field, success_msg, failure_msg
	):
		if not self.get(field) or not is_image(self.get(field)):
			frappe.msgprint(failure_msg, alert=True, indicator="orange")
			return

		self.set(width, flt(self.get(width)))
		self.set(height, flt(self.get(height)))

		# To preserve the aspect ratio of the image, apply constraints only on
		# the greater dimension and allow the other to scale accordingly
		dimension = "width" if self.get(width) > self.get(height) else "height"
		dimension_value = self.get(f"{dimension_prefix}{dimension}")

		if not dimension_value:
			dimension_value = ""

		self.set(
			html_field,
			f"""<div style="text-align: {self.get(align, "").lower()};">
<img src="{self.get(field)}" alt="{self.get("name")}"
{dimension}="{dimension_value}" style="{dimension}: {dimension_value}px;">
</div>""",
		)

		frappe.msgprint(success_msg, alert=True)
