# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class CustomLink(Document):
	pass

def get_custom_doctype_links(doctype, data):
	if frappe.get_all("Custom Link", {"document_type": doctype}):
		doc = frappe.get_doc("Custom Link", doctype)

		if not data.transactions:
			# init groups
			data.transactions = []
			data.non_standard_fieldnames = {}

		for link in doc.links:
			link.added = False
			for group in data.transactions:
				# group found
				if group.get("label") == link.group:
					if not link.link_doctype in group.get("items"):
						group.get("items").append(link.link_doctype)
					link.added = True

			if not link.added:
				# group not found, make a new group
				data.transactions.append({
					"label": link.group,
					"items": [link.link_doctype]
				})

			if link.link_fieldname != data.fieldname:
				if data.fieldname:
					data.non_standard_fieldnames[link.link_doctype] = link.link_fieldname
				else:
					data.fieldname = link.link_fieldname

	return data