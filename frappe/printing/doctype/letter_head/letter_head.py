# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from typing import Tuple

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, is_image


class LetterHead(Document):
	def before_insert(self):
		# for better UX, let user set from attachment
		self.source = "Image"

	def validate(self):
		self.set_image()
		self.validate_disabled_and_default()

	def validate_disabled_and_default(self):
		if self.disabled and self.is_default:
			frappe.throw(_("Letter Head cannot be both disabled and default"))

		if not self.is_default and not self.disabled:
			if not frappe.db.exists("Letter Head", dict(is_default=1)):
				self.is_default = 1

	def set_image(self):
		if self.source == "Image":
			self.set_image_as_html(
				**{
					"field": "image",
					"width": "image_width",
					"height": "image_height",
					"align": "align",
					"html_field": "content",
					"dimension_prefix": "image_",
					"success_msg": _("Header HTML set from attachment {0}").format(self.image),
					"failure_msg": _("Please attach an image file to set HTML for Letter Head.")
				}
			)

		if self.footer_source == "Image":
			self.set_image_as_html(
				**{
					"field": "footer_image",
					"width": "footer_image_width",
					"height": "footer_image_height",
					"align": "footer_align",
					"html_field": "footer",
					"dimension_prefix": "footer_image_",
					"success_msg": _("Footer HTML set from attachment {0}").format(self.footer_image),
					"failure_msg": _("Please attach an image file to set HTML for Footer.")
				}
			)

	def set_image_as_html(self, **kwargs):
		if self.get(kwargs.get("field")) and is_image(self.get(kwargs.get("field"))):
			self.set(kwargs.get("width"), flt(self.get(kwargs.get("width"))))
			self.set(kwargs.get("height"), flt(self.get(kwargs.get("height"))))
			dimension, dimension_value = self.get_dimension(
				kwargs.get("width"), kwargs.get("height"), kwargs.get("dimension_prefix")
			)


			html = f"""
				<div style="text-align: {self.get(kwargs.get("align"), "").lower()};">
					<img src="{self.get(kwargs.get("field"))}" alt="{self.get("name")}"
					{dimension}="{dimension_value}" style="{dimension}: {dimension_value}px;">
				</div>
			"""

			self.set(kwargs.get("html_field"), html)

			frappe.msgprint(kwargs.get("success_msg"), alert=True)
		else:
			frappe.msgprint(kwargs.get("failure_msg"), alert=True, indicator="orange")

	def get_dimension(self, width: float, height: float, prefix: str) -> Tuple[str, float]:
		"""
		Preserves the aspect ratio of the image for either Letterhead or Footer.
		To preserve the aspect ratio the contraints are only applied on dimension
		with the greater size and allow the other dimension to scale accordingly
		"""

		dimension = "width" if width > height else "height"
		return dimension, self.get(f"{prefix}{dimension}")

	def on_update(self):
		self.set_as_default()

		# clear the cache so that the new letter head is uploaded
		frappe.clear_cache()

	def set_as_default(self):
		from frappe.utils import set_default

		if self.is_default:
			frappe.db.sql("update `tabLetter Head` set is_default=0 where name != %s", self.name)

			set_default("letter_head", self.name)

			# update control panel - so it loads new letter directly
			frappe.db.set_default("default_letter_head_content", self.content)
		else:
			frappe.defaults.clear_default("letter_head", self.name)
			frappe.defaults.clear_default("default_letter_head_content", self.content)
