# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

from frappe.model.document import Document

class WebsiteSlideshow(Document):
	def on_update(self):
		# a slide show can be in use and any change in it should get reflected
		from frappe.website.render import clear_cache
		clear_cache()

def get_slideshow(doc):
	if not doc.slideshow:
		return {}

	slideshow = frappe.get_doc("Website Slideshow", doc.slideshow)

	return {
		"slides": slideshow.get({"doctype":"Website Slideshow Item"}),
		"slideshow_header": slideshow.header or ""
	}
