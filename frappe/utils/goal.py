# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def get_goal_doctype_monthly_results(goal_doctype, goal_field, aggregation = 'sum'):
	''''''

	results = frappe.db.sql('''
		select
			{0}({1}) as {1}, date_format(creation, '%m-%Y') as month_year
		from
			`{2}`
		where
			status != 'Draft'
		group by
			month_year'''.format(aggregation, goal_field, "tab" + goal_doctype), as_dict=True)

	month_to_value_dict = {}
	for d in results:
		month_to_value_dict[d['month_year']] = d[goal_field]

	return month_to_value_dict

@frappe.whitelist()
def get_goal_graph_data(title, doctype, docname, goal_value_field, goal_total_field,
	goal_doctype, goal_field, aggregation="sum"):
	''''''

	month_to_value_dict = get_goal_doctype_monthly_results(goal_doctype, goal_field, aggregation)

	from frappe.utils import today, getdate, formatdate, add_months
	months = []
	values = []
	for i in xrange(0, 12):
		month_value = formatdate(add_months(today(), -i), "MM-yyyy")
		month_word = getdate(month_value).strftime('%b')
		months.insert(0, month_word)
		if month_value in month_to_value_dict:
			values.insert(0, month_to_value_dict[month_value])
		else:
			values.insert(0, 0)

	current_month_year = formatdate(today(), "MM-yyyy")
	current_month_value = 0
	if current_month_year in month_to_value_dict:
		current_month_value = month_to_value_dict[current_month_year]

	# Set doc completed goal value
	frappe.db.set_value(doctype, docname, goal_total_field, current_month_value)

	goal = frappe.get_value(doctype, docname, goal_value_field)

	data = {
		'title': title,
		# 'subtitle':
		'y_values': values,
		'x_points': months,
		'specific_values': [
			{
				'name': "Goal",
				'line_type': "dashed",
				'value': goal
			},
		],
	}

	return data