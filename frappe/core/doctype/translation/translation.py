# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.translate import clear_cache
from frappe.utils import strip_html_tags, is_html
import json

class Translation(Document):
	def validate(self):
		if is_html(self.source_name):
			self.remove_html_from_source()

	def remove_html_from_source(self):
		self.source_name = strip_html_tags(self.source_name).strip()

	def on_update(self):
		clear_cache()

	def on_trash(self):
		clear_cache()

@frappe.whitelist()
def contribute_translation(language, contributor, source_name, target_name):
	data = {"data": json.dumps({
		"language": language,
		"contributor": contributor,
		"source_name": source_name,
		"target_name": target_name,
		"posting_date": frappe.utils.nowdate()
	})}
	from frappe.integrations.utils import make_post_request
	try:
		response = make_post_request(url=frappe.get_hooks("translation_contribution_url")[0], data=data)
	except Exception:
		frappe.msgprint("Something went wrong while contributing translation. Please check error log for more details")
	if response.get("message") == "Already exists":
		frappe.msgprint("Translation already exists")
	elif response.get("message") == "Added to contribution list":
		frappe.msgprint("Translation successfully contributed")
