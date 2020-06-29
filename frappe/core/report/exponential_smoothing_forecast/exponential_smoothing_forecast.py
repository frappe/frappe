# Copyright (c) 2013, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.utils import flt, gzip_decompress, getdate

def execute(filters=None):
	return ForecastingReport(filters).execute_report()

class ForecastingReport(object):
	def __init__(self, filters=None):
		self.filters = filters

	def execute_report(self):
		self.validate_filters()
		self.prepare_report_data()

		columns = self.get_columns()
		charts = self.get_chart_data()
		summary_data = self.get_summary_data()

		return columns, self.data, None, charts, summary_data

	def validate_filters(self):
		if not self.filters.forecast_template:
			frappe.throw(_("Forecast Template is required to generate the forecast data"))

	def prepare_report_data(self):
		self.forecast_doc = frappe.get_doc("Forecast Template", self.filters.forecast_template)
		attached_file_name = frappe.db.get_value("File", {
			"attached_to_doctype": self.forecast_doc.doctype,
			"attached_to_name":self.forecast_doc.name
		}, "name")

		if attached_file_name:
			attached_file = frappe.get_doc('File', attached_file_name)
			compressed_content = attached_file.get_content()
			uncompressed_content = gzip_decompress(compressed_content)
			self.data = json.loads(uncompressed_content)
		else:
			self.forecast_doc.prepare_forecast_data(auto_commit=True)
			self.data = self.forecast_doc.data

	def get_columns(self):
		columns = []
		for column in self.forecast_doc.columns:
			columns.append({
				"label": _(column.field_label),
				"options": column.field_options,
				"fieldname": column.fieldname,
				"fieldtype": column.field_type,
				"width": column.width or 120
			})

		self.forecast_doc.prepare_period_list()

		parent, fieldname = self.forecast_doc.forecast_field.split(',')
		self.fieldtype = frappe.db.get_value("DocField", {
			"parent": parent,
			"fieldname": fieldname
		}, "fieldtype")

		width = 180 if self.forecast_doc.periodicity in ['Yearly', "Half-Yearly", "Quarterly"] else 100
		for period in self.forecast_doc.period_list:
			if (self.forecast_doc.periodicity in ['Yearly', "Half-Yearly", "Quarterly"]
				or period.from_date >= getdate(self.forecast_doc.from_date)):

				forecast_key = period.key
				label = _(period.label)
				if period.from_date >= getdate(self.forecast_doc.from_date):
					forecast_key = 'forecast_' + period.key
					label = _(period.label) + " " + _("(Forecast)")

				columns.append({
					"label": label,
					"fieldname": forecast_key,
					"fieldtype": self.fieldtype,
					"width": width,
					"default": 0.0
				})

		return columns

	def get_chart_data(self):
		if not self.data: return

		labels = []
		self.total_demand = []
		self.total_forecast = []
		self.total_history_forecast = []
		self.total_future_forecast = []

		for period in self.forecast_doc.period_list:
			forecast_key = "forecast_" + period.key

			labels.append(_(period.label))

			if period.from_date < getdate(self.forecast_doc.from_date):
				self.total_demand.append(self.data[-1].get(period.key, 0))
				self.total_history_forecast.append(self.data[-1].get(forecast_key, 0))
			else:
				self.total_future_forecast.append(self.data[-1].get(forecast_key, 0))

			self.total_forecast.append(self.data[-1].get(forecast_key, 0))

		return {
			"data": {
				"labels": labels,
				"datasets": [
					{
						"name": "Demand",
						"values": self.total_demand
					},
					{
						"name": "Forecast",
						"values": self.total_forecast
					}
				]
			},
			"type": "line"
		}

	def get_summary_data(self):
		if not self.data: return

		return [
			{
				"value": sum(self.total_demand),
				"label": _("Total Demand (Past Data)"),
				"datatype": self.fieldtype
			},
			{
				"value": sum(self.total_history_forecast),
				"label": _("Total Forecast (Past Data)"),
				"datatype": self.fieldtype
			},
			{
				"value": sum(self.total_future_forecast),
				"indicator": "Green",
				"label": _("Total Forecast (Future Data)"),
				"datatype": self.fieldtype
			}
		]