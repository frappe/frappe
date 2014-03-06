# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os, time
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.utils import cleanup_page_name
from frappe.utils import cint

class DocType(WebsiteGenerator):
	def __init__(self, doc, doclist):
		self.doc, self.doclist = doc, doclist
		self.save_versions = True