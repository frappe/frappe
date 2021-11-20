# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import is_image, flt
from frappe.model.document import Document
from frappe import _

class LetterHead(Document):
	def before_insert(self):
		# for better UX, let user set from attachment
		self.source = 'Image'

	def validate(self):
		self.set_image()
		self.validate_disabled_and_default()

	def validate_disabled_and_default(self):
		if self.disabled and self.is_default:
			frappe.throw(_("Letter Head cannot be both disabled and default"))

		if not self.is_default and not self.disabled:
			if not frappe.db.exists('Letter Head', dict(is_default=1)):
				self.is_default = 1

	def set_image(self):
		if self.source=='Image':
			if self.image and is_image(self.image):
				self.image_width = flt(self.image_width)
				self.image_height = flt(self.image_height)
				dimension = 'width' if self.image_width > self.image_height else 'height'
				dimension_value = self.get('image_' + dimension)
				self.content = f'''
				<div style="text-align: {self.align.lower()};">
					<img src="{self.image}" alt="{self.name}" {dimension}="{dimension_value}" style="{dimension}: {dimension_value}px;">
				</div>
				'''
				frappe.msgprint(frappe._('Header HTML set from attachment {0}').format(self.image), alert = True)
			else:
				frappe.msgprint(frappe._('Please attach an image file to set HTML'), alert = True, indicator = 'orange')

	def on_update(self):
		self.set_as_default()

		# clear the cache so that the new letter head is uploaded
		frappe.clear_cache()

	def set_as_default(self):
		from frappe.utils import set_default
		if self.is_default:
			frappe.db.sql("update `tabLetter Head` set is_default=0 where name != %s",
				self.name)

			set_default('letter_head', self.name)

			# update control panel - so it loads new letter directly
			frappe.db.set_default("default_letter_head_content", self.content)
		else:
			frappe.defaults.clear_default('letter_head', self.name)
			frappe.defaults.clear_default("default_letter_head_content", self.content)
