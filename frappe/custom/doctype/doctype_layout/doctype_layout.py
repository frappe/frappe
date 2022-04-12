# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

from frappe.desk.utils import slug
from frappe.model.document import Document


class DocTypeLayout(Document):
	def validate(self):
		if not self.route:
			self.route = slug(self.name)
