# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Goal(Document):
	def fetch_fields(self):
		if not self.source:
			return

		meta = frappe.get_meta(self.source)

		print meta.get("fields")
		return {
			"source_filter": meta.get_list_fields(),
			"based_on": [d.fieldname for d in meta.get_numeric_fields()]
		}

	def validate(self):
		# Check for conflicting goals
		pass

@frappe.whitelist()
def get_doc_count(doctype, filters = {}, time_slot = {}):
	print "/" * 40
	return len(frappe.get_list(doctype, filters=filters))

@frappe.whitelist()
def get_value_aggregation(doctype, field, filters = {}, time_slot = {}):
	field_value_list = [d[field] for d in frappe.get_list(doctype,
		fields = [field], filters=filters)]
	sum = sum(field_value_list)
	average = sum / len(field_value_list)

	return {
		"value_list": field_value_list,
		"sum": sum,
		"average": average
	}

@frappe.whitelist()
def get_count_summary(doctype, frequency, count, filters = {}):
	summaries = []
	for t in create_time_slots(frequency, count):
		summaries.append({
			"time_slot": t,
			"count": get_doc_count(doctype, filters, t)
		})
	return summaries

@frappe.whitelist()
def get_aggregation_summary(doctype, field, frequency, count, filters = {}):
	summaries = []
	for t in create_time_slots(frequency, count):
		summaries.append({
			"time_slot": t,
			"aggregation": get_value_aggregation(doctype, field, filters, t)
		})
	return summaries

def create_time_slots(frequency, count):
	# create time slots
	# For "Daily",
	# [
	# 	{
	# 		"start":,
	# 		"end":,
	# 	},
	# 	{
	# 		"start":,
	# 		"end":,
	# 	}
	# ]
	return []
