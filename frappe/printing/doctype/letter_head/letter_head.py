# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import is_image


from frappe.model.document import Document

class LetterHead(Document):
	def before_insert(self):
		# for better UX, let user set from attachment
		self.source = 'Image'

	def validate(self):
		self.set_image()
		if not self.is_default:
			if not frappe.db.sql("""select count(*) from `tabLetter Head` where ifnull(is_default,0)=1"""):
				self.is_default = 1

	def set_image(self):
		if self.source=='Image':
			if self.image and is_image(self.image):
				self.content = '<img src="{}" style="width: 100%;">'.format(self.image)
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