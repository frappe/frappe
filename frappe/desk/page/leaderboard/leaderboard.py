# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import frappe
from frappe.utils import add_to_date


@frappe.whitelist()
def get_leaderboard_config():
	leaderboard_config = frappe._dict()
	leaderboard_hooks = frappe.get_hooks('leaderboards')
	for hook in leaderboard_hooks:
		leaderboard_config.update(frappe.get_attr(hook)())

	return leaderboard_config

@frappe.whitelist()
def get_leaderboards(leaderboard_config, doctype, timespan, company, field, limit):
	limit = frappe.parse_json(limit)
	leaderboard_config = frappe.parse_json(leaderboard_config)
	from_date = get_from_date(timespan)
	method = leaderboard_config[doctype]['method']
	records = frappe.get_attr(method)(from_date, company, field, limit)

	return records

def get_from_date(selected_timespan):
	"""return string for ex:this week as date:string"""
	days = months = years = 0
	if "month" == selected_timespan.lower():
		months = -1
	elif "quarter" == selected_timespan.lower():
		months = -3
	elif "year" == selected_timespan.lower():
		years = -1
	elif "week" == selected_timespan.lower():
		days = -7
	else:
		return ''

	return add_to_date(None, years=years, months=months, days=days,
		as_string=True, as_datetime=True)