# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class WebsiteMetaTag(Document):
	def get_content(self):
		# can't have new lines in meta content
		return (self.value or '').replace('\n', ' ')

def set_metatags(meta_tags, context):
	context.setdefault('metatags', frappe._dict({}))

	for row in meta_tags:
		context.metatags[row.key] = row.get_content()

	return context