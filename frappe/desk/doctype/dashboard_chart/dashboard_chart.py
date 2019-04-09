# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.core.page.dashboard.dashboard import cache_source, get_from_date_from_timespan
from frappe.utils import nowdate, add_to_date, getdate, get_first_day, get_last_day
from frappe.model.document import Document

@frappe.whitelist()
@cache_source
def get(chart_name, filters=None):
	chart = frappe.get_doc('Dashboard Chart', chart_name)
	timespan = chart.timespan
	timegrain = chart.time_interval
	date_function = {
		'Monthly': 'month',
		'Quarterly': 'quarter',
		'Weekly': 'week',
		'Daily': 'dayofyear'
	}[timegrain]
	interval_unit = 'day' if date_function=='dayofyear' else date_function

	filters['docstatus'] = ('<', 2)
	from_date = get_from_date_from_timespan(timespan)

	conditions, values = frappe.db.build_conditions(filters)

	# build and run query

	# query will return last day of the interval and aggregate value
	data = frappe.db.sql('''
		select
			date_sub(date_add(makedate(year({datefield}), 1), interval {interval_unit}({datefield}) {interval_unit}), interval 1 day) as date,
			{aggregate_function}({value_field})
		from `tab{doctype}`
		where
			{conditions}
			and {datefield} >= '{from_date}'
			and {datefield} <= curdate()
		group by {date_function}({datefield}), year({datefield})
		order by {datefield} asc
	'''.format(
		date_function = date_function,
		datefield = chart.based_on,
		aggregate_function = chart.chart_type,
		value_field = chart.value_based_on or '1',
		doctype = chart.document_type,
		conditions = conditions,
		from_date = from_date.strftime('%Y-%m-%d'),
		interval_unit = interval_unit
	), values)

	result = add_missing_values(data, timegrain)

	return {
		"labels": [r[0].strftime('%Y-%m-%d') for r in result],
		"datasets": [{
			"name": chart.name,
			"values": [r[1] for r in result]
		}]
	}

def add_missing_values(data, timegrain):
	# add missing intervals
	result = []

	def get_next_expected_date(date):
		next_date = None
		if timegrain=='Daily':
			next_date = add_to_date(date, days=1)
		elif timegrain=='Weekly':
			next_date = add_to_date(date, days=7)
		elif timegrain=='Monthly':
			next_date = get_last_day(add_to_date(get_first_day(date), months=1))
		elif timegrain=='Quarterly':
			next_date = get_last_day(add_to_date(get_first_day(date), months=3))

		return getdate(next_date)

	for i, d in enumerate(data):
		result.append(d)

		next_expected_date = get_next_expected_date(d[0])

		if i < len(data)-1:
			next_date = data[i+1][0]
		else:
			# already reached at end of data, see if we need any more dates
			next_date = getdate(nowdate())

		# if next data point is earler than the expected date
		# need to fill out missing data points
		while next_date > next_expected_date:
			# fill missing value
			result.append([next_expected_date, 0.0])
			next_expected_date = get_next_expected_date(next_expected_date)

	return result

class DashboardChart(Document):
	pass

