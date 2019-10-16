# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
from datetime import datetime
from croniter import croniter
import re
import frappe
from frappe.desk.query_report import run as execute_report
from frappe.utils import nowdate, cstr, cint
from frappe.modules.export_file import export_to_files
from six import string_types
from frappe.report.utils import get_column_def

class ReportSnapshot(Document):

	def validate(self):
		if not self.report:
			frappe.throw('Report name is mandatory')
		self.report_config = frappe.db.get_value(
			'Report', self.report, ['is_standard', 'module', 'disabled'], as_dict=1)

		self.validate_standard()

		self.validate_disabled()

		if self.get("cron_string") and not croniter.is_valid(self.get("cron_string")):
			frappe.throw("Enter valid Cron string")

	def validate_standard(self):
		if self.is_standard == 'Yes':
			if self.report_config.is_standard == 'No':
				frappe.throw(
					'Standard Report Snapshot must have standard Report')

	def validate_disabled(self):
		if (not cint(self.disabled)) and cint(self.report_config.disabled):
			frappe.throw('Report {self.report} is disabled'.format(self=self))

	def before_save(self):
		if not self.doc_type:
			self.doc_type = frappe.unscrub(
				frappe.scrub(self.name)) + " Snapshot"
		if self.is_standard == 'Yes' and not self.module:
			self.module = self.report_config.module

	def on_update(self):
		if self.is_standard == 'Yes' and self.module and frappe.local.conf.developer_mode and not frappe.flags.in_migrate:
			export_to_files(record_list=[[self.doctype, self.name]],
							record_module=self.module, create_init=True)

	# columns : list of columns from report
	def create_or_update_doctype(self, columns):

		# set because it takes only unique name and provides difference functionality
		# new_field_names = set([1,2,3,4,5,1,1,4])
		# new_field_names = {1,2,3,4,5}
		# doctype_fields = {1,2,3}
		# final_list = new_field_names - doctype_fields
		# output: final_list = {4,5}

		_columns = { remove_special_char(field.get('fieldname')): field for field in columns}

		new_field_names = set([remove_special_char(
			field.get('fieldname')) for field in columns])
		doc = None
		doc_name = frappe.db.get_value('DocType', self.doc_type)

		if self.doc_type and doc_name:
			doc = frappe.get_doc('DocType', doc_name)
			fields = doc.fields
			# this is to take only those fields which are new
			new_field_names = new_field_names - \
				set([field.fieldname for field in fields])

		if not new_field_names:
			return

		if not doc and not doc_name:
			doc = frappe.get_doc({
				'doctype': 'DocType',
				'__newname': self.doc_type,
				'name': self.doc_type,
				'module': 'Core',
				'autoname': "hash",
				'custom': cint(self.is_standard != 'Yes'),
				'track_changes': 0,
				'in_create': 1,
				'__islocal': 1,
			})

			doc.append('permissions', {
				'role': 'System Manager',
				'read': 1,
				'write': 1,
				'create': 1,
				'report': 1,
				'export': 1,
			})

			doc.append('fields', {
				'label': "Snapshot Date",
				'in_list_view': 1,
				'fieldtype': 'Date',
				'fieldname': '__date',
				'read_only': 1,
			})

		# update fields in doc, with new fields
		for field in new_field_names:
			doc.append('fields', {
				'label': frappe.unscrub(field),
				'fieldtype': _columns[remove_special_char(field)]["fieldtype"] or "Data",
				'fieldname': remove_special_char(field),
				'read_only': 1,
				'in_list_view': 1,
				'options': _columns[remove_special_char(field)]["options"] or "",
			})

		try:
			doc.save(ignore_permissions=True)
			frappe.db.commit()
			frappe.db.sql(f"""ALTER TABLE `tab{self.doc_type}` MODIFY name BIGINT not null AUTO_INCREMENT""")
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Error while creating Snapshot doctype - {e}")
			frappe.db.rollback()


@frappe.whitelist()
def take_snapshot(docname):
	frappe.utils.background_jobs.enqueue(
		execute, queue="long", docname=docname)
	frappe.msgprint('Enqueued')


def get_data(doc):
	"""
		This function fetches data required to create snapshot.
	"""

	report_res = frappe._dict()

	filters = frappe._dict({
		row.field_name: frappe.render_template(row.field_value, {
			'frappe': frappe,
		}) if '{{' in row.field_value else row.field_value
		for row in doc.filters
	})

	report_res = frappe._dict(execute_report(doc.report, filters))

	return report_res


def create_snapshot(doc, report_res, columns):
	"""
		This function creates snapshot for the fetched data.
		Creation of snapshot has following kinds of behaviour:-
			1.  Replace
			2.  Filter based update
			3.  Append
	"""

	# Filter based update - filtered data from snapshot table is deleted and then replaced with new data
	if doc.filter_based_update:
		delete_snapshot_based_on_filter(doc)

	# Replace - snapshot table will be truncated and entirely replaced with new data.
	if doc.replace_old_snapshot:
		frappe.db.sql('truncate `tab{0}`;'.format(doc.doc_type))

	# insert data :-
	# snapshot_insert(report_res, columns, doc)
	# db_insert :-
	# snapshot_db_insert(report_res, columns, doc)
	# bulk_insert :-
	bulk_insert(report_res.result, columns, doc)


def snapshot_insert(report_res, columns, doc):

	for row in report_res.result:
		data_dict = None
		if not isinstance(row, dict):
			data_dict = {
				remove_special_char(col.get('fieldname')): cstr(row[idx]) for idx, col in enumerate(columns)
			}
		else:
			data_dict = row
		data_dict.update({
			'doctype': doc.doc_type,
			'__date': nowdate(),
		})

		snap_doc = frappe.get_doc(frappe._dict(data_dict))
		snap_doc.flags.ignore_permissions = True
		snap_doc.insert()


def snapshot_db_insert(report_res, columns, doc):

	for row in report_res.result:
		data_dict = None
		if not isinstance(row, dict):
			data_dict = {
				remove_special_char(col.get('fieldname')): cstr(row[idx]) for idx, col in enumerate(columns)
			}
		else:
			data_dict = row
		data_dict.update({
			'doctype': doc.doc_type,
			'__date': nowdate(),
		})

		snap_doc = frappe.get_doc(frappe._dict(data_dict))
		snap_doc.flags.ignore_permissions = True
		snap_doc.db_insert()


def bulk_insert(data, columns, doc):

	columns = [remove_special_char(col.get('fieldname')) for idx, col in enumerate(columns)]
	columns.append('__date')

	values = []
	for row in data:
		row_arr = list(row)
		row_arr.append(nowdate())
		row = tuple(row_arr)
		val_arr = [cstr(row[idx]) for idx, col in enumerate(columns)]
		val_string = tuple(val_arr)
		values.append(val_string)

	bulk_insert_query = frappe.db.sql("""
		INSERT INTO `tab{doctype}`
		({columns})
		VALUES {values}
	""".format(
		doctype=doc.doc_type,
		columns=", ".join(["`" + c + "`" for c in columns]),
		values=", ".join(str(v) for v in values)
	), debug=1)


def execute(docname=None, doc=None):

	if docname:
		doc = frappe.get_doc('Report Snapshot', docname)

	if not doc:
		frappe.throw("Report Snapshot document not found")

	if doc.disabled:
		frappe.throw("Report Snapshot is disabled")
		return

	# Get data for snapshot creation
	report_res = get_data(doc)

	if not report_res or not report_res.columns or not report_res.result:
		return

	columns = get_column_def(report_res.columns)

	doc.create_or_update_doctype(columns)

	# Create snapshots
	create_snapshot(doc, report_res, columns)


def remove_special_char(name):

	# columns in report are generally in the form column_name:Datatype:width
	# so "column_name:Datatype:width".split(':')[0] will return column_name
	name = name.split(':')[0]
	name = name.replace(' ', '_').strip().lower()

	# re.sub replace all the match with ''
	name = re.sub("[\W]", '', name, re.UNICODE)
	return name


def run_hourly():
	now = frappe.utils.now_datetime()
	hour = now.hour

	frappe.log_error({
		'msg': 'Running report snapshot at {0} hour'.format(hour),
		'job_name': 'Report Snapshot',
		'function_name': 'report_snapshot.run_hourly'
	}, 'report_snapshot.run_hourly')

	for config in frappe.get_all("Report Snapshot", filters={"at_hour": hour, "disabled": 0, "schedule": "At Hour"}):
		take_snapshot(config.name)


def cron_run():
	#	frappe.logger().debug("CRON CALLED")
	now = frappe.utils.now_datetime()

	for config in frappe.get_all("Report Snapshot", filters={"schedule": "Cron_String", "disabled": 0}, fields=["name", "cron_string"]):
		if config.get("cron_string") and (croniter(config.get("cron_string")).get_next(datetime) <= now):
			take_snapshot(config.name)


def delete_snapshot_based_on_filter(doc):
	filters = doc.get('snapshot_filters')
	if not filters:
		return
	filters = convert_filters_to_condition_str(filters)
	delete_query = f"""
		DELETE
		FROM `tab{doc.get('doc_type')}`
		WHERE {filters}
	"""
	response = frappe.db.sql(delete_query)
	return response


def convert_filters_to_condition_str(filters):
	condition = ' AND '.join(
		[f'{filter.key} {filter.op} {filter.value}' if isinstance(
			filter.value, (int, float)) else f'{filter.key} {filter.op} "{filter.value}" ' for filter in filters]
	)
	condition = frappe.render_template(condition, {'frappe': frappe})
	return condition