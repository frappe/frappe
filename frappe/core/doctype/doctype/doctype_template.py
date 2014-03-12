# Copyright (c) 2013, {app_publisher}
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl