# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import datetime
from frappe.core.page.dashboard.dashboard import cache_source, get_from_date_from_timespan
from frappe.utils import nowdate, add_to_date, getdate, get_last_day, formatdate
from frappe.model.document import Document

@frappe.whitelist()
@cache_source
def get(chart, no_cache=None, from_date=None, to_date=None, refresh = None):

	chart = frappe.parse_json(chart)
	timespan = chart.timespan
	timegrain = chart.time_interval
	filters = frappe.parse_json(chart.filters_json)

	# don't include cancelled documents
	filters['docstatus'] = ('<', 2)

	if not from_date:
		from_date = get_from_date_from_timespan(to_date, timespan)
	if not to_date:
		to_date = datetime.datetime.now()

	# get conditions from filters
	conditions, values = frappe.db.build_conditions(filters)

	# query will return year, unit and aggregate value
	data = frappe.db.sql('''
		select
			extract(year from {datefield}) as _year,
			{unit_function} as _unit,
			{aggregate_function}({value_field})
		from `tab{doctype}`
		where
			{conditions}
			and {datefield} >= '{from_date}'
			and {datefield} <= '{to_date}'
		group by _year, _unit
		order by _year asc, _unit asc
	'''.format(
		unit_function = get_unit_function(chart.based_on, timegrain),
		datefield = chart.based_on,
		aggregate_function = get_aggregate_function(chart.chart_type),
		value_field = chart.value_based_on or '1',
		doctype = chart.document_type,
		conditions = conditions,
		from_date = from_date.strftime('%Y-%m-%d'),
		to_date = to_date
	), values)

	# result given as year, unit -> convert it to end of period of that unit
	result = convert_to_dates(data, timegrain)

	# add missing data points for periods where there was no result
	result = add_missing_values(result, timegrain, from_date, to_date)

	return {
		"labels": [formatdate(r[0].strftime('%Y-%m-%d')) for r in result],
		"datasets": [{
			"name": chart.name,
			"values": [r[1] for r in result]
		}]
	}

def get_aggregate_function(chart_type):
	return {
		"Sum": "SUM",
		"Count": "COUNT",
		"Average": "AVG"
	}[chart_type]

def convert_to_dates(data, timegrain):
	result = []
	for d in data:
		if timegrain == 'Daily':
			result.append([add_to_date('{:d}-01-01'.format(int(d[0])), days = d[1] - 1), d[2]])
		elif timegrain == 'Weekly':
			result.append([add_to_date(add_to_date('{:d}-01-01'.format(int(d[0])), weeks = d[1] + 1), days = -1), d[2]])
		elif timegrain == 'Monthly':
			result.append([add_to_date(add_to_date('{:d}-01-01'.format(int(d[0])), months = d[1]), days = -1), d[2]])
		elif timegrain == 'Quarterly':
			result.append([add_to_date(add_to_date('{:d}-01-01'.format(int(d[0])), months = d[1] * 3), days = -1), d[2]])

		result[-1][0] = getdate(result[-1][0])

	return result

def get_unit_function(datefield, timegrain):
	unit_function = ''
	if timegrain=='Daily':
		if frappe.db.db_type == 'mariadb':
			unit_function = 'dayofyear({})'.format(datefield)
		else:
			unit_function = 'extract(doy from {datefield})'.format(
				datefield=datefield)

	else:
		unit_function = 'extract({unit} from {datefield})'.format(
			unit = timegrain[:-2].lower(), datefield=datefield)

	return unit_function

def add_missing_values(data, timegrain, from_date, to_date):
	# add missing intervals
	result = []

	first_expected_date = get_period_ending(from_date, timegrain)

	# fill out data before the first data point
	first_data_point_date = data[0][0] if data else getdate(add_to_date(to_date, days=1))
	while first_data_point_date > first_expected_date:
		result.append([first_expected_date, 0.0])
		first_expected_date = get_next_expected_date(first_expected_date, timegrain)

	# fill data points and missing points
	for i, d in enumerate(data):
		result.append(d)

		next_expected_date = get_next_expected_date(d[0], timegrain)

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
			next_expected_date = get_next_expected_date(next_expected_date, timegrain)

	# add date for the last period (if missing)
	if result and get_period_ending(to_date, timegrain) > result[-1][0]:
		result.append([get_period_ending(to_date, timegrain), 0.0])

	return result

def get_next_expected_date(date, timegrain):
	next_date = None
	if timegrain=='Daily':
		next_date = add_to_date(date, days=1)
	else:
		# given date is always assumed to be the period ending date
		next_date = get_period_ending(add_to_date(date, days=1), timegrain)
	return getdate(next_date)

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
	# fun fact: week ends on the day before 1st Jan of the year.
	# for 2019 it is Monday

	week_of_the_year = int(date.strftime('%U'))
	# first day of next week
	date = add_to_date('{}-01-01'.format(date.year), weeks = week_of_the_year + 1)
	# last day of this week
	return add_to_date(date, days = -1)

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


class DashboardChart(Document):
	def on_update(self):
		frappe.cache().delete_key('chart-data:{}'.format(self.name))

	def validate(self):
		if self.chart_type != 'Custom':
			self.check_required_field()

	def check_required_field(self):
		if not self.based_on:
			frappe.throw(_("Time series based on is required to create a dashboard chart"))
		if not self.document_type:
			frappe.throw(_("Document type is required to create a dashboard chart"))
