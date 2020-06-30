# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _
from frappe.core.doctype.file.file import remove_file
from frappe.utils import (cint, add_months, add_days,
	get_months, flt, nowdate, add_years, getdate, formatdate)
from six import string_types
from frappe.desk.form.load import get_meta_bundle
from frappe.utils.background_jobs import enqueue
from frappe.core.doctype.prepared_report.prepared_report import create_json_gz_file
from frappe.core.doctype.forecast_template.prepare_forecasting_data import ExponentialSmoothingForecast
from frappe.model.document import Document

get_months_to_add = {
	"Yearly": 12,
	"Half-Yearly": 6,
	"Quarterly": 3,
	"Monthly": 1
}

class ForecastTemplate(Document, ExponentialSmoothingForecast):
	def validate(self):
		self.validate_dates()
		self.remove_old_file()

	def validate_dates(self):
		if self.from_date > self.to_date:
			frappe.throw(_("From Date should not be greater than To Date"))

	def remove_old_file(self):
		if self.status == 'Completed' and not self.is_new():
			attached_file_name = frappe.db.get_value("File", {
				"attached_to_doctype": self.doctype,
				"attached_to_name":self.name
			}, "name")

			frappe.db.set_value("File", attached_file_name, {
				"attached_to_doctype": None,
				"attached_to_name": None
			})

			enqueue(delete_doc_file, name=attached_file_name, timeout=6000)

			self.status = "Open"

	def prepare_forecast_data(self, auto_commit=False):
		self.based_on_doctype, self.based_on_field = self.forecast_field.split(',')

		self.prepare_period_list()
		self.prepare_periodical_data()
		self.forecast_future_data()
		self.prepare_final_data()
		self.add_total()

		json_filename = "{0}-{1}.json.gz".format(
			self.name, frappe.utils.data.format_datetime(frappe.utils.now(), "Y-m-d-H:M")
		)

		create_json_gz_file(self.data, "Forecast Template", self.name, json_filename)

		if auto_commit:
			frappe.db.set_value("Forecast Template", self.name, "status", "Completed")
			frappe.db.commit()

	def prepare_period_list(self):
		from_date = add_years(self.from_date, cint(self.based_on_past_data) * -1)
		self.period_list = get_period_list(from_date, self.to_date, self.periodicity)

	def prepare_periodical_data(self):
		self.key_fields = []
		self.period_wise_data = {}

		order_data = self.get_data_for_forecast() or []

		for entry in order_data:
			key = self.prepare_key(entry)
			if key not in self.period_wise_data:
				self.period_wise_data[key] = entry

			period_data = self.period_wise_data[key]
			for period in self.period_list:
				# check if posting date is within the period
				if (entry.posting_date >= period.from_date and entry.posting_date <= period.to_date):
					period_data[period.key] = period_data.get(period.key, 0.0) + flt(entry.get(self.based_on_field))

		list_of_period_value = []
		for key, value in self.period_wise_data.items():
			if self.forecasting_method == "Single Exponential Smoothing":
				list_of_period_value = [value.get(p.key, 0) for p in self.period_list]
			else:
				if not list_of_period_value:
					self.get_average_value_for_seasonal(value, list_of_period_value)

			if list_of_period_value:
				total_qty = [1 for d in list_of_period_value if d]
				if total_qty:
					value["avg"] = flt(sum(list_of_period_value)) / flt(sum(total_qty))

	def get_average_value_for_seasonal(self, value, list_of_period_value):
		self.starting_period = None
		for p in self.period_list:
			if value.get(p.key, 0):
				self.starting_period = p
				break

		if not self.starting_period: return

		for p in self.period_list:
			if (p.current_period_start_date == self.starting_period.current_period_start_date and
				p.current_period_end_date == self.starting_period.current_period_end_date):
				list_of_period_value.append(value.get(p.key, 0))

	def get_data_for_forecast(self):
		filters = self.forecast_filters or []
		fields = self.get_forecast_fields()
		if filters and isinstance(filters, string_types):
			filters = json.loads(filters)

		return frappe.get_all(self.document_type, fields=fields, filters=filters, debug=1)

	def get_forecast_fields(self):
		fields = []
		for d in self.columns:
			field = '`tab{0}`.{1}'.format(d.document_type, d.fieldname)
			fields.append(field)
			self.key_fields.append(d.fieldname)

		# forecast field
		fields.append('`tab{0}`.{1}'.format(self.based_on_doctype, self.based_on_field))

		# date field
		fields.append('`tab{0}`.{1} as posting_date'.format(self.document_type, self.date_field))

		return fields

	def prepare_key(self, row):
		key = []
		for field in self.key_fields:
			key.append(row.get(field))

		return tuple(key)

	def prepare_final_data(self):
		self.data = []

		if not self.period_wise_data: return

		for key in self.period_wise_data:
			self.data.append(self.period_wise_data.get(key))

	def add_total(self):
		if not self.data: return

		field = self.key_fields[0]
		total_row = {
			field: _(frappe.bold("Total Quantity"))
		}

		for value in self.data:
			for period in self.period_list:
				forecast_key = "forecast_" + period.key
				if forecast_key not in total_row:
					total_row.setdefault(forecast_key, 0.0)

				if period.key not in total_row:
					total_row.setdefault(period.key, 0.0)

				total_row[forecast_key] += value.get(forecast_key, 0.0)
				total_row[period.key] += value.get(period.key, 0.0)

		self.data.append(total_row)

def delete_doc_file(name):
	frappe.delete_doc("File", name, ignore_permissions=True)

def get_doctypes(doctype, txt, searchfield, start, page_len, filters):
	modules = frappe.get_all("Module Def", filters = {
		"app_name": ["not in", ["frappe"]]
	}, as_list=1)

	modules = [m[0] for m in modules]

	return frappe.get_all("DocType", filters = {
		"module": ["in", modules], "istable": 0, "name": ("like", "%%%s%%" % txt)
	}, as_list=1)

@frappe.whitelist()
def get_doctype_fields(doctype):
	if not hasattr(frappe.local, 'doctype_fields_with_child'):
		frappe.local.doctype_fields_with_child = {}

	if not doctype in frappe.local.doctype_fields_with_child:
		meta = get_meta_bundle(doctype)
		fields = []

		for data in meta:
			fields.extend(data.fields)

		frappe.local.doctype_fields_with_child[doctype] = fields

	doctype_fields = frappe.local.doctype_fields_with_child[doctype]

	return sorted(doctype_fields, key=lambda field:field.label)

@frappe.whitelist()
def get_field_details(doctype, label):
	field_doctype, fieldname = label.split(',')

	fields = get_doctype_fields(doctype)
	for field in fields:
		if field.fieldname == fieldname and field.parent == field_doctype:
			return field

@frappe.whitelist()
def prepare_forecast_data(docname):
	frappe.db.set_value("Forecast Template", docname, {
		"status": "In Progress",
		"error_message": None
	})

	enqueue(make_forecast_data, name=docname, timeout=6000)

def make_forecast_data(name):
	doc = frappe.get_doc("Forecast Template", name)
	try:
		doc.remove_old_file()
		doc.prepare_forecast_data()
		frappe.db.set_value("Forecast Template", name, "status", "Completed")
	except:
		frappe.log_error(frappe.get_traceback())
		frappe.db.set_value("Forecast Template", name, {
			"status": "Error",
			"error_message": frappe.get_traceback()
		})

def get_period_list(period_start_date, period_end_date, periodicity):
	"""Get a list of dict {"from_date": from_date, "to_date": to_date, "key": key, "label": label}
		Periodicity can be (Yearly, Quarterly, Monthly)"""

	year_start_date = getdate(period_start_date)
	year_end_date = getdate(period_end_date)

	months_to_add = get_months_to_add.get(periodicity)

	period_list = []

	start_date = year_start_date
	months = get_months(year_start_date, year_end_date)

	if (months // months_to_add) != (months / months_to_add):
		months += months_to_add

	no_of_slots_in_year = 12.0 / months_to_add

	count = 0
	for i in range(months // months_to_add):
		period = frappe._dict({
			"from_date": start_date
		})

		if count % no_of_slots_in_year == 0:
			current_period_start_date = start_date
			current_period_end_date = add_months(start_date, 12)

		period.current_period_start_date = current_period_start_date
		period.current_period_end_date = current_period_end_date
		count +=1

		to_date = add_months(start_date, months_to_add)
		start_date = to_date

		# Subtract one day from to_date, as it may be first day in next fiscal year or month
		to_date = add_days(to_date, -1)

		if to_date <= year_end_date:
			# the normal case
			period.to_date = to_date
		else:
			# if a fiscal year ends before a 12 month period
			period.to_date = year_end_date

		period_list.append(period)

		if period.to_date == year_end_date:
			break

	# common processing
	for opts in period_list:
		key = opts["to_date"].strftime("%b_%Y").lower()
		if periodicity == "Monthly":
			label = formatdate(opts["to_date"], "MMM YYYY")
		else:
			label = get_label(periodicity, opts["from_date"], opts["to_date"])

		last_period_end_date = add_months(opts["to_date"], -12)

		opts.update({
			"key": key.replace(" ", "_").replace("-", "_"),
			"label": label,
			"year_start_date": year_start_date,
			"year_end_date": year_end_date,
			"last_period_key": last_period_end_date.strftime("%b_%Y").lower(),
		})

	return period_list

def get_label(periodicity, from_date, to_date):
	if periodicity == "Yearly":
		if formatdate(from_date, "YYYY") == formatdate(to_date, "YYYY"):
			label = formatdate(from_date, "YYYY")
		else:
			label = formatdate(from_date, "YYYY") + "-" + formatdate(to_date, "YYYY")
	else:
		label = formatdate(from_date, "MMM YY") + "-" + formatdate(to_date, "MMM YY")

	return label