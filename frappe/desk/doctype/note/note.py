# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Note(Document):
	def autoname(self):
		# replace forbidden characters
		import re
		self.name = re.sub("[%'\"#*?`]", "", self.title.strip())

	def before_print(self):
		self.print_heading = self.name
		self.sub_heading = ""

def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	if user == "Administrator":
		return ""

	return """(`tabNote`.public=1 or `tabNote`.owner="{user}")""".format(user=user)

def has_permission(doc, ptype, user):
	if doc.public == 1 or user == "Administrator":
		return True

	if user == doc.owner:
		return True

	return False
