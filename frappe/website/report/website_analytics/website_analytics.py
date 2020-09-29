# Copyright (c) 2013, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from datetime import datetime
from frappe.utils import getdate
from frappe.utils.dateutils import get_dates_from_timegrain

def execute(filters=None):
	return WebsiteAnalytics(filters).run()

class WebsiteAnalytics(object):
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})

		if not self.filters.to_date:
			self.filters.to_date = datetime.now()

		if not self.filters.from_date:
			self.filters.from_date = frappe.utils.add_days(self.filters.to_date, -7)

		if not self.filters.range:
			self.filters.range = "Daily"

		self.filters.to_date = frappe.utils.add_days(self.filters.to_date, 1)
		self.query_filters = {'creation': ['between', [self.filters.from_date, self.filters.to_date]]}

	def run(self):
		columns = self.get_columns()
		data = self.get_data()
		chart = self.get_chart_data()
		summary = self.get_report_summary()

		return columns, data[:250], None, chart, summary

	def get_columns(self):
		return [
			{
				"fieldname": "path",
				"label": "Page",
				"fieldtype": "Data",
				"width": 300
			},
			{
				"fieldname": "count",
				"label": "Page Views",
				"fieldtype": "Int",
				"width": 150
			},
			{
				"fieldname": "unique_count",
				"label": "Unique Visitors",
				"fieldtype": "Int",
				"width": 150
			}
		]

	def get_data(self):
		pg_query = """
				SELECT
					path,
					COUNT(*) as count,
					COUNT(CASE WHEN CAST(is_unique as Integer) = 1 THEN 1 END) as unique_count
				FROM `tabWeb Page View`
				WHERE  coalesce("tabWeb Page View".creation, '0001-01-01') BETWEEN %s AND %s
				GROUP BY path
				ORDER BY count desc
			"""

		mariadb_query = """
				SELECT
					path,
					COUNT(*) as count,
					COUNT(CASE WHEN is_unique = 1 THEN 1 END) as unique_count
				FROM `tabWeb Page View`
				WHERE creation BETWEEN %s AND %s
				GROUP BY path
				ORDER BY count desc
			"""

		data = frappe.db.multisql({
				"mariadb": mariadb_query,
				"postgres": pg_query
			}, (self.filters.from_date, self.filters.to_date))
		return data

	def _get_query_for_mariadb(self):
		filters_range = self.filters.range
		field = 'creation'
		date_format = '%Y-%m-%d'

		if filters_range == "Weekly":
			field = 'ADDDATE(creation, INTERVAL 1-DAYOFWEEK(creation) DAY)'

		elif filters_range == "Monthly":
			date_format = '%Y-%m-01'

		query = """
				SELECT
					DATE_FORMAT({0}, %s) as date,
					COUNT(*) as count,
					COUNT(CASE WHEN is_unique = 1 THEN 1 END) as unique_count
				FROM `tabWeb Page View`
				WHERE creation BETWEEN %s AND %s
				GROUP BY DATE_FORMAT({0}, %s)
				ORDER BY creation
			""".format(field)

		values = (date_format, self.filters.from_date, self.filters.to_date, date_format)

		return query, values

	def _get_query_for_postgres(self):
		filters_range = self.filters.range
		field = 'creation'
		granularity = 'day'

		if filters_range == "Weekly":
			granularity = 'week'

		elif filters_range == "Monthly":
			granularity = 'day'

		query = """
				SELECT
					DATE_TRUNC(%s, {0}) as date,
					COUNT(*) as count,
					COUNT(CASE WHEN CAST(is_unique as Integer) = 1 THEN 1 END) as unique_count
				FROM "tabWeb Page View"
				WHERE  coalesce("tabWeb Page View".{0}, '0001-01-01') BETWEEN %s AND %s
				GROUP BY date_trunc(%s, {0})
				ORDER BY date
			""".format(field)

		values = (granularity, self.filters.from_date, self.filters.to_date, granularity)

		return query, values

	def get_chart_data(self):
		current_dialect = frappe.db.db_type or 'mariadb'

		if current_dialect == 'mariadb':
			query, values = self._get_query_for_mariadb()
		else:
			query, values = self._get_query_for_postgres()

		self.chart_data = frappe.db.sql(query, values=values, as_dict=1)

		return self.prepare_chart_data(self.chart_data)

	def prepare_chart_data(self, data):
		date_range = get_dates_from_timegrain(self.filters.from_date, self.filters.to_date, self.filters.range)
		if self.filters.range == "Monthly":
			date_range = [frappe.utils.add_days(dd, 1) for dd in date_range]

		labels = []
		total_dataset = []
		unique_dataset = []

		def get_data_for_date(date):
			for item in data:
				item_date = getdate(item.get("date"))
				if item_date == date:
					return item
			return {'count': 0, 'unique_count': 0}


		for date in date_range:
			labels.append(date.strftime("%b %d %Y"))
			match = get_data_for_date(date)
			total_dataset.append(match.get('count', 0))
			unique_dataset.append(match.get('unique_count', 0))

		chart = {
			"data": {
				'labels': labels,
				'datasets': [
					{
						'name': "Total Views",
						'type': 'line',
						'values': total_dataset
					},
					{
						'name': "Unique Visits",
						'type': 'line',
						'values': unique_dataset
					}
				]
			},
			"type": "axis-mixed",
			'lineOptions': {
				'regionFill': 1,
			},
			'axisOptions': {
				'xIsSeries': 1
			},
			'colors': ['#7cd6fd', '#5e64ff']
		}

		return chart


	def get_report_summary(self):
		total_count = 0
		unique_count = 0
		for data in self.chart_data:
			unique_count += data.get('unique_count')
			total_count += data.get('count')

		report_summary = [
			{
				"value": total_count,
				"label": "Total Page Views",
				"datatype": "Int",
			},
			{
				"value": unique_count,
				"label": "Unique Page Views",
				"datatype": "Int",
			},

		]
		return report_summary