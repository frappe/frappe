# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class DynamicLink(Document):
	pass

def on_doctype_update():
	frappe.db.add_index("Dynamic Link", ["link_doctype", "link_name"])

def deduplicate_dynamic_links(doc):
	links, duplicate = [], False
	for l in doc.links or []:
		t = (l.link_doctype, l.link_name)
		if not t in links:
			links.append(t)
		else:
			duplicate = True

	if duplicate:
		doc.links = []
		for l in links:
			doc.append('links', dict(link_doctype=l[0], link_name=l[1]))
