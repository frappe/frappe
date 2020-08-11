# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json, datetime
from frappe import _, scrub
import frappe.desk.query_report
from frappe.utils import cint, cstr
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files
from frappe.modules import make_boilerplate
from frappe.core.doctype.page.page import delete_custom_role
from frappe.core.doctype.custom_role.custom_role import get_custom_allowed_roles
from frappe.desk.reportview import append_totals_row
from six import iteritems
from frappe.utils.safe_exec import safe_exec


class Report(Document):
	def validate(self):
		"""only administrator can save standard report"""
		if not self.module:
			self.module = frappe.db.get_value("DocType", self.ref_doctype, "module")

		if not self.is_standard:
			self.is_standard = "No"
			if frappe.session.user=="Administrator" and getattr(frappe.local.conf, 'developer_mode',0)==1:
				self.is_standard = "Yes"

		if self.is_standard == "No":
			# allow only script manager to edit scripts
			if self.report_type != 'Report Builder':
				frappe.only_for('Script Manager', True)

			if frappe.db.get_value("Report", self.name, "is_standard") == "Yes":
				frappe.throw(_("Cannot edit a standard report. Please duplicate and create a new report"))

		if self.is_standard == "Yes" and frappe.session.user!="Administrator":
			frappe.throw(_("Only Administrator can save a standard report. Please rename and save."))

		if self.report_type == "Report Builder":
			self.update_report_json()

	def before_insert(self):
		self.set_doctype_roles()

	def on_update(self):
		self.export_doc()

	def on_trash(self):
		delete_custom_role('report', self.name)

	def set_doctype_roles(self):
		if not self.get('roles') and self.is_standard == 'No':
			meta = frappe.get_meta(self.ref_doctype)
			roles = [{'role': d.role} for d in meta.permissions if d.permlevel==0]
			self.set('roles', roles)

	def is_permitted(self):
		"""Returns true if Has Role is not set or the user is allowed."""
		from frappe.utils import has_common

		allowed = [d.role for d in frappe.get_all("Has Role", fields=["role"],
			filters={"parent": self.name})]

		custom_roles = get_custom_allowed_roles('report', self.name)
		allowed.extend(custom_roles)

		if not allowed:
			return True

		if has_common(frappe.get_roles(), allowed):
			return True

	def update_report_json(self):
		if not self.json:
			self.json = '{}'

	def export_doc(self):
		if frappe.flags.in_import:
			return

		if self.is_standard == 'Yes' and (frappe.local.conf.get('developer_mode') or 0) == 1:
			export_to_files(record_list=[['Report', self.name]],
				record_module=self.module, create_init=True)

			self.create_report_py()

	def create_report_py(self):
		if self.report_type == "Script Report":
			make_boilerplate("controller.py", self, {"name": self.name})
			make_boilerplate("controller.js", self, {"name": self.name})

	def execute_query_report(self, filters):
		if not self.query:
			frappe.throw(_("Must specify a Query to run"), title=_('Report Document Error'))

		if not self.query.lower().startswith("select"):
			frappe.throw(_("Query must be a SELECT"), title=_('Report Document Error'))

		result = [list(t) for t in frappe.db.sql(self.query, filters)]
		columns = [cstr(c[0]) for c in frappe.db.get_description()]

		return [columns, result]

	def execute_script_report(self, filters):
		# save the timestamp to automatically set to prepared
		threshold = 30
		res = []

		start_time = datetime.datetime.now()

		# The JOB
		if self.is_standard == 'Yes':
			res = self.execute_module(filters)
		else:
			res = self.execute_script(filters)

		# automatically set as prepared
		execution_time = (datetime.datetime.now() - start_time).total_seconds()
		if execution_time > threshold and not self.prepared_report:
			self.db_set('prepared_report', 1)

		frappe.cache().hset('report_execution_time', self.name, execution_time)

		return res

	def execute_module(self, filters):
		# report in python module
		module = self.module or frappe.db.get_value("DocType", self.ref_doctype, "module")
		method_name = get_report_module_dotted_path(module, self.name) + ".execute"
		return frappe.get_attr(method_name)(frappe._dict(filters))

	def execute_script(self, filters):
		# server script
		loc = {"filters": frappe._dict(filters), 'data':[]}
		safe_exec(self.report_script, None, loc)
		return loc['data']

	def get_data(self, filters=None, limit=None, user=None, as_dict=False, ignore_prepared_report=False):
		columns = []
		out = []

		if self.report_type in ('Query Report', 'Script Report', 'Custom Report'):
			# query and script reports
			data = frappe.desk.query_report.run(self.name,
				filters=filters, user=user, ignore_prepared_report=ignore_prepared_report)

			for d in data.get('columns'):
				if isinstance(d, dict):
					col = frappe._dict(d)
					if not col.fieldname:
						col.fieldname = col.label
					columns.append(col)
				else:
					fieldtype, options = "Data", None
					parts = d.split(':')
					if len(parts) > 1:
						if parts[1]:
							fieldtype, options = parts[1], None
							if fieldtype and '/' in fieldtype:
								fieldtype, options = fieldtype.split('/')

					columns.append(frappe._dict(label=parts[0], fieldtype=fieldtype, fieldname=parts[0], options=options))

			out += data.get('result')
		else:
			# standard report
			params = json.loads(self.json)

			if params.get('fields'):
				columns = params.get('fields')
			elif params.get('columns'):
				columns = params.get('columns')
			elif params.get('fields'):
				columns = params.get('fields')
			else:
				columns = [['name', self.ref_doctype]]
				for df in frappe.get_meta(self.ref_doctype).fields:
					if df.in_list_view:
						columns.append([df.fieldname, self.ref_doctype])

			_filters = params.get('filters') or []

			if filters:
				for key, value in iteritems(filters):
					condition, _value = '=', value
					if isinstance(value, (list, tuple)):
						condition, _value = value
					_filters.append([key, condition, _value])

			def _format(parts):
				# sort by is saved as DocType.fieldname, covert it to sql
				return '`tab{0}`.`{1}`'.format(*parts)

			if params.get('sort_by'):
				order_by = _format(params.get('sort_by').split('.')) + ' ' + params.get('sort_order')
			elif params.get('order_by'):
				order_by = params.get('order_by')
			else:
				order_by = _format([self.ref_doctype, 'modified']) + ' desc'

			if params.get('sort_by_next'):
				order_by += ', ' + _format(params.get('sort_by_next').split('.')) + ' ' + params.get('sort_order_next')

			result = frappe.get_list(self.ref_doctype,
				fields = [_format([c[1], c[0]]) for c in columns],
				filters=_filters,
				order_by = order_by,
				as_list=True,
				limit=limit,
				user=user)

			_columns = []

			for (fieldname, doctype) in columns:
				meta = frappe.get_meta(doctype)

				if meta.get_field(fieldname):
					field = meta.get_field(fieldname)
				else:
					field = frappe._dict(fieldname=fieldname, label=meta.get_label(fieldname))
					# since name is the primary key for a document, it will always be a Link datatype
					if fieldname == "name":
						field.fieldtype = "Link"
						field.options = doctype

				_columns.append(field)
			columns = _columns

			out = out + [list(d) for d in result]

			if params.get('add_totals_row'):
				out = append_totals_row(out)

		if as_dict:
			data = []
			for row in out:
				if isinstance(row, (list, tuple)):
					_row = frappe._dict()
					for i, val in enumerate(row):
						_row[columns[i].get('fieldname')] = val
				elif isinstance(row, dict):
					# no need to convert from dict to dict
					_row = frappe._dict(row)
				data.append(_row)
		else:
			data = out
		return columns, data


	@Document.whitelist
	def toggle_disable(self, disable):
		self.db_set("disabled", cint(disable))

@frappe.whitelist()
def is_prepared_report_disabled(report):
	return frappe.db.get_value('Report',
		report, 'disable_prepared_report') or 0

def get_report_module_dotted_path(module, report_name):
	return frappe.local.module_app[scrub(module)] + "." + scrub(module) \
		+ ".report." + scrub(report_name) + "." + scrub(report_name)
