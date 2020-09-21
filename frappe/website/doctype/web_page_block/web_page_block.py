# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class WebPageBlock(Document):

	def render(self):
		web_template = frappe.get_doc("Web Template", self.web_template)
		return web_template.render(self.web_template_values)
