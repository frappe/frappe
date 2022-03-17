# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document

from frappe.desk.utils import slug

class DocTypeLayout(Document):
	def validate(self):
		if not self.route:
			self.route = slug(self.name)
