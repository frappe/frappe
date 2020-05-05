# Copyright (c) 2013, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.dateutils import get_date_range

def execute(filters=None):
	return WebsiteAnalytics(filters).run()

class WebsiteAnalytics(object):
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.filters.to_date = frappe.utils.add_days(self.filters.to_date, 1)
		self.query_filters = {'creation': ['between', [self.filters.from_date, self.filters.to_date]]}

	def run(self):
		columns = self.get_columns()
		data = self.get_data()
		chart = self.get_chart_data()
		summary = self.get_report_summary()
		return columns, data, None, chart, summary

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
			}
		]

	def get_data(self):
		data = frappe.get_all("Web Page View", fields=['path', 'count(*) as count'], filters=self.query_filters, group_by="path", order_by='count desc')
		return data

	def get_chart_data(self):
		def _get_field_for_chart(filters_range):
			field = 'creation'
			date_format = '%Y-%m-%d'

			if filters_range == "W":
				field = 'ADDDATE(creation, INTERVAL 1-DAYOFWEEK(creation) DAY)'

			elif filters_range == "M":
				date_format = '%Y-%m-01'

			return field, date_format

		field, date_format = _get_field_for_chart(self.filters.range)

		self.chart_data = frappe.db.sql("""
				SELECT
					DATE_FORMAT({0}, %s) as date,
					COUNT(*) as count,
					count(CASE WHEN is_unique = 1 THEN 1 END) as unique_count
				FROM `tabWeb Page View`
				WHERE creation BETWEEN %s AND %s
				GROUP BY DATE_FORMAT({0}, %s)
				ORDER BY creation
			""".format(field), (date_format, self.filters.from_date, self.filters.to_date, date_format), as_dict=1)

		return self.prepare_chart_data(self.chart_data)

	def prepare_chart_data(self, data):
		date_range = get_date_range(self.filters.from_date, self.filters.to_date, self.filters.range)
		if self.filters.range == "M":
			date_range = [frappe.utils.add_days(dd, 1) for dd in date_range]

		labels = []
		total_dataset = []
		unique_dataset = []

		def get_data_for_date(date):
			for item in data:
				item_date = frappe.utils.get_datetime(item.get("date")).date()
				if item_date == date.date():
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
			}
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