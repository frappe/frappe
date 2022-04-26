# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class WebsiteMetaTag(Document):
	def get_content(self):
		# can't have new lines in meta content
		return (self.value or "").replace("\n", " ")

	def get_meta_dict(self):
		return {self.key: self.get_content()}

	def set_in_context(self, context):
		context.setdefault("metatags", frappe._dict({}))
		context.metatags[self.key] = self.get_content()
		return context
