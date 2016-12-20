# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class KanbanBoard(Document):
	pass

@frappe.whitelist()
def update_column(board_name, column_title):
	'''
	Adds new column to Kanban Board's child table `columns`
	'''
	doc = frappe.get_doc("Kanban Board", board_name)
	doc.append("columns", dict(
		column_name=column_title,
		color=""
	))
	doc.save()
	return doc