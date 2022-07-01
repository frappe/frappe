# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.desk.utils import slug
from frappe.model.document import Document


class DocTypeLayout(Document):
	def validate(self):
		if not self.route:
			self.route = slug(self.name)
