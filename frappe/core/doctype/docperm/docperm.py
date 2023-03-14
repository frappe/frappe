# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class DocPerm(Document):
	def before_save(self):
		if self.is_new():
			pass

	def on_trash(self):
		pass
