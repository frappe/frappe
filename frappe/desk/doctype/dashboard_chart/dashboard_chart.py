# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import datetime
<<<<<<< HEAD
from frappe.core.page.dashboard.dashboard import cache_source, get_from_date_from_timespan
from frappe.utils import nowdate, add_to_date, getdate, get_last_day, formatdate
=======
import json
from frappe.utils.dashboard import cache_source
from frappe.utils import nowdate, getdate, get_datetime, cint, now_datetime
from frappe.utils.dateutils import\
	get_period, get_period_beginning, get_from_date_from_timespan, get_dates_from_timegrain
from frappe.model.naming import append_number_if_name_exists
from frappe.boot import get_allowed_reports
>>>>>>> 969aa86e68... fix: calculate chart data from beginning of period
from frappe.model.document import Document

@frappe.whitelist()
@cache_source
def get(chart_name = None, chart = None, no_cache = None, from_date = None, to_date = None, refresh = None):
	if chart_name:
		chart = frappe.get_doc('Dashboard Chart', chart_name)
	else:
		chart = frappe._dict(frappe.parse_json(chart))

	timespan = chart.timespan

	if chart.timespan == 'Select Date Range':
		from_date = chart.from_date
		to_date = chart.to_date

	timegrain = chart.time_interval
	filters = frappe.parse_json(chart.filters_json)

	# don't include cancelled documents
	filters['docstatus'] = ('<', 2)

	if chart.chart_type == 'Group By':
		chart_config = get_group_by_chart_config(chart, filters)
	else:
		chart_config =  get_chart_config(chart, filters, timespan, timegrain, from_date, to_date)

	return chart_config


def get_chart_config(chart, filters, timespan, timegrain, from_date, to_date):
	if not from_date:
		from_date = get_from_date_from_timespan(to_date, timespan)
		from_date = get_period_beginning(from_date, timegrain)
	if not to_date:
<<<<<<< HEAD
		to_date = datetime.datetime.now()

	# get conditions from filters
	conditions, values = frappe.db.build_conditions(filters)
	# query will return year, unit and aggregate value
	data = frappe.db.sql('''
		select
			{unit} as _unit,
			{aggregate_function}({value_field})
		from `tab{doctype}`
		where
			{conditions}
			and {datefield} BETWEEN '{from_date}' and '{to_date}'
		group by _unit
		order by _unit asc
	'''.format(
		unit = chart.based_on,
		datefield = chart.based_on,
		aggregate_function = get_aggregate_function(chart.chart_type),
		value_field = chart.value_based_on or '1',
		doctype = chart.document_type,
		conditions = conditions,
		from_date = from_date.strftime('%Y-%m-%d'),
		to_date = to_date
	), values)

	# add missing data points for periods where there was no result
=======
		to_date = now_datetime()

	doctype = chart.document_type
	datefield = chart.based_on
	aggregate_function = get_aggregate_function(chart.chart_type)
	value_field = chart.value_based_on or '1'
	from_date = from_date.strftime('%Y-%m-%d')
	to_date = to_date

	filters.append([doctype, datefield, '>=', from_date, False])
	filters.append([doctype, datefield, '<=', to_date, False])

	data = frappe.db.get_list(
		doctype,
		fields = [
			'{} as _unit'.format(datefield),
			'{aggregate_function}({value_field})'.format(aggregate_function=aggregate_function, value_field=value_field),
		],
		filters = filters,
		group_by = '_unit',
		order_by = '_unit asc',
		as_list = True,
		ignore_ifnull = True
	)

>>>>>>> 969aa86e68... fix: calculate chart data from beginning of period
	result = get_result(data, timegrain, from_date, to_date)

	chart_config = {
		"labels": [get_period(r[0], timegrain) for r in result],
		"datasets": [{
			"name": chart.name,
			"values": [r[1] for r in result]
		}]
	}

	return chart_config


def get_group_by_chart_config(chart, filters):
	conditions, values = frappe.db.build_conditions(filters)
	data = frappe.db.sql('''
		select
			{aggregate_function}({value_field}) as count,
			{group_by_field} as name
		from `tab{doctype}`
		where {conditions}
		group by {group_by_field}
		order by count desc
	'''.format(
		aggregate_function = get_aggregate_function(chart.group_by_type),
		value_field = chart.aggregate_function_based_on or '1',
		field = chart.aggregate_function_based_on or chart.group_by_based_on,
		group_by_field = chart.group_by_based_on,
		doctype = chart.document_type,
		conditions = conditions,
	), values, as_dict = True)

	if data:
		if chart.number_of_groups and chart.number_of_groups < len(data):
			other_count = 0
			for i in range(chart.number_of_groups - 1, len(data)):
				other_count += data[i]['count']
			data = data[0: chart.number_of_groups - 1]
			data.append({'name': 'Other', 'count': other_count})

		chart_config = {
			"labels": [item['name'] if item['name'] else 'Not Specified' for item in data],
			"datasets": [{
				"name": chart.name,
				"values": [item['count'] for item in data]
			}]
		}
		return chart_config
	else:
		return None


def get_aggregate_function(chart_type):
	return {
		"Sum": "SUM",
		"Count": "COUNT",
		"Average": "AVG",
	}[chart_type]

def get_result(data, timegrain, from_date, to_date):
	dates = get_dates_from_timegrain(from_date, to_date, timegrain)
	result = [[date, 0] for date in dates]
	data_index = 0
	if data:
		for i, d in enumerate(result):
			while data_index < len(data) and getdate(data[data_index][0]) <= d[0]:
				d[1] += data[data_index][1]
				data_index += 1

	return result

<<<<<<< HEAD

def get_next_expected_date(date, timegrain):
	next_date = None

	# given date is always assumed to be the period ending date
	next_date = get_period_ending(add_to_date(date, days=1), timegrain)
	return getdate(next_date)

<<<<<<< HEAD
def get_period_beginning(date, timegrain):
	as_str = True
	if timegrain == 'Daily':
		pass
	elif timegrain == 'Weekly':
		date = get_first_day_of_week(date, as_str=as_str)
	elif timegrain == 'Monthly':
		date = get_first_day(date, as_str=as_str)
	elif timegrain == 'Quarterly':
		date = get_quarter_start(date, as_str=as_str)
	elif timegrain == 'Yearly':
		date = get_year_start(date, as_str=as_str)

	return date

def get_period_ending(date, timegrain):
	date = getdate(date)
	if timegrain=='Daily':
		pass
	elif timegrain=='Weekly':
		date = get_week_ending(date)
	elif timegrain=='Monthly':
		date = get_month_ending(date)
	elif timegrain=='Quarterly':
		date = get_quarter_ending(date)

	return getdate(date)

def get_week_ending(date):
	# week starts on monday
	from datetime import timedelta
	start = date - timedelta(days = date.weekday())
	end = start + timedelta(days=6)

	return end

def get_month_ending(date):
	month_of_the_year = int(date.strftime('%m'))
	# first day of next month (note month starts from 1)

	date = add_to_date('{}-01-01'.format(date.year), months = month_of_the_year)
	# last day of this month
	return add_to_date(date, days = -1)

def get_quarter_ending(date):
	date = getdate(date)

	# find the earliest quarter ending date that is after
	# the given date
	for month in (3, 6, 9, 12):
		quarter_end_month = getdate('{}-{}-01'.format(date.year, month))
		quarter_end_date = getdate(get_last_day(quarter_end_month))
		if date <= quarter_end_date:
			date = quarter_end_date
			break

	return date

=======
=======
>>>>>>> 8fde766b8f... fix: use get_dates_from_timegrain function
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_charts_for_user(doctype, txt, searchfield, start, page_len, filters):
	or_filters = {'owner': frappe.session.user, 'is_public': 1}
	return frappe.db.get_list('Dashboard Chart',
		fields=['name'],
		filters=filters,
		or_filters=or_filters,
		as_list = 1)
>>>>>>> 7f43169c4a... refactor: reorganise date functions indashboard_chart.py

class DashboardChart(Document):
	def on_update(self):
		frappe.cache().delete_key('chart-data:{}'.format(self.name))

	def validate(self):
		if self.chart_type != 'Custom':
			self.check_required_field()

	def check_required_field(self):
		if not self.document_type:
				frappe.throw(_("Document type is required to create a dashboard chart"))

		if self.chart_type == 'Group By':
			if not self.group_by_based_on:
				frappe.throw(_("Group By field is required to create a dashboard chart"))
			if self.group_by_type in ['Sum', 'Average'] and not self.aggregate_function_based_on:
				frappe.throw(_("Aggregate Function field is required to create a dashboard chart"))
		else:
			if not self.based_on:
				frappe.throw(_("Time series based on is required to create a dashboard chart"))
