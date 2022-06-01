# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import datetime
import json

from six import iteritems

import frappe
import frappe.desk.query_report
from frappe import _, scrub
from frappe.core.doctype.custom_role.custom_role import get_custom_allowed_roles
from frappe.core.doctype.page.page import delete_custom_role
from frappe.desk.reportview import append_totals_row
from frappe.model.document import Document
from frappe.modules import make_boilerplate
from frappe.modules.export_file import export_to_files
from frappe.utils import cint, cstr
from frappe.utils.safe_exec import safe_exec


class Report(Document):
	def validate(self):
		"""only administrator can save standard report"""
		if not self.module:
			self.module = frappe.db.get_value("DocType", self.ref_doctype, "module")

		if not self.is_standard:
			self.is_standard = "No"
			if (
				frappe.session.user == "Administrator" and getattr(frappe.local.conf, "developer_mode", 0) == 1
			):
				self.is_standard = "Yes"

		if self.is_standard == "No":
			# allow only script manager to edit scripts
			if self.report_type != "Report Builder":
				frappe.only_for("Script Manager", True)

			if frappe.db.get_value("Report", self.name, "is_standard") == "Yes":
				frappe.throw(_("Cannot edit a standard report. Please duplicate and create a new report"))

		if self.is_standard == "Yes" and frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can save a standard report. Please rename and save."))

		if self.report_type == "Report Builder":
			self.update_report_json()

	def before_insert(self):
		self.set_doctype_roles()

	def on_update(self):
		self.export_doc()

	def on_trash(self):
		if (
			self.is_standard == "Yes"
			and not cint(getattr(frappe.local.conf, "developer_mode", 0))
			and not frappe.flags.in_patch
		):
			frappe.throw(_("You are not allowed to delete Standard Report"))
		delete_custom_role("report", self.name)
		self.delete_prepared_reports()

	def delete_prepared_reports(self):
		prepared_reports = frappe.get_all(
			"Prepared Report", filters={"ref_report_doctype": self.name}, pluck="name"
		)

		for report in prepared_reports:
			frappe.delete_doc(
				"Prepared Report", report, ignore_missing=True, force=True, delete_permanently=True
			)

	def get_columns(self):
		return [d.as_dict(no_default_fields=True) for d in self.columns]

	@frappe.whitelist()
	def set_doctype_roles(self):
		if not self.get("roles") and self.is_standard == "No":
			meta = frappe.get_meta(self.ref_doctype)
			if not meta.istable:
				roles = [{"role": d.role} for d in meta.permissions if d.permlevel == 0]
				self.set("roles", roles)

	def is_permitted(self):
		"""Returns true if Has Role is not set or the user is allowed."""
		from frappe.utils import has_common

		allowed = [
			d.role for d in frappe.get_all("Has Role", fields=["role"], filters={"parent": self.name})
		]

		custom_roles = get_custom_allowed_roles("report", self.name)

		if custom_roles:
			allowed = custom_roles

		if not allowed:
			return True

		if has_common(frappe.get_roles(), allowed):
			return True

	def update_report_json(self):
		if not self.json:
			self.json = "{}"

	def export_doc(self):
		if frappe.flags.in_import:
			return

		if self.is_standard == "Yes" and (frappe.local.conf.get("developer_mode") or 0) == 1:
			export_to_files(
				record_list=[["Report", self.name]], record_module=self.module, create_init=True
			)

			self.create_report_py()

	def create_report_py(self):
		if self.report_type == "Script Report":
			make_boilerplate("controller.py", self, {"name": self.name})
			make_boilerplate("controller.js", self, {"name": self.name})

	def execute_query_report(self, filters):
		if not self.query:
			frappe.throw(_("Must specify a Query to run"), title=_("Report Document Error"))

		if not self.query.lower().startswith("select"):
			frappe.throw(_("Query must be a SELECT"), title=_("Report Document Error"))

		result = [list(t) for t in frappe.db.sql(self.query, filters)]
		columns = self.get_columns() or [cstr(c[0]) for c in frappe.db.get_description()]

		return [columns, result]

	def execute_script_report(self, filters):
		# save the timestamp to automatically set to prepared
		threshold = 30
		res = []

		start_time = datetime.datetime.now()

		# The JOB
		if self.is_standard == "Yes":
			res = self.execute_module(filters)
		else:
			res = self.execute_script(filters)

		# automatically set as prepared
		execution_time = (datetime.datetime.now() - start_time).total_seconds()
		if execution_time > threshold and not self.prepared_report:
			self.db_set("prepared_report", 1)

		frappe.cache().hset("report_execution_time", self.name, execution_time)

		return res

	def execute_module(self, filters):
		# report in python module
		module = self.module or frappe.db.get_value("DocType", self.ref_doctype, "module")
		method_name = get_report_module_dotted_path(module, self.name) + ".execute"
		return frappe.get_attr(method_name)(frappe._dict(filters))

	def execute_script(self, filters):
		# server script
		loc = {"filters": frappe._dict(filters), "data": None, "result": None}
		safe_exec(self.report_script, None, loc)
		if loc["data"]:
			return loc["data"]
		else:
			return self.get_columns(), loc["result"]

	def get_data(
		self, filters=None, limit=None, user=None, as_dict=False, ignore_prepared_report=False
	):
		if self.report_type in ("Query Report", "Script Report", "Custom Report"):
			columns, result = self.run_query_report(filters, user, ignore_prepared_report)
		else:
			columns, result = self.run_standard_report(filters, limit, user)

		if as_dict:
			result = self.build_data_dict(result, columns)

		return columns, result

	def run_query_report(self, filters, user, ignore_prepared_report=False):
		columns, result = [], []
		data = frappe.desk.query_report.run(
			self.name, filters=filters, user=user, ignore_prepared_report=ignore_prepared_report
		)

		for d in data.get("columns"):
			if isinstance(d, dict):
				col = frappe._dict(d)
				if not col.fieldname:
					col.fieldname = col.label
				columns.append(col)
			else:
				fieldtype, options = "Data", None
				parts = d.split(":")
				if len(parts) > 1:
					if parts[1]:
						fieldtype, options = parts[1], None
						if fieldtype and "/" in fieldtype:
							fieldtype, options = fieldtype.split("/")

				columns.append(
					frappe._dict(label=parts[0], fieldtype=fieldtype, fieldname=parts[0], options=options)
				)

		result += data.get("result")

		return columns, result

	def run_standard_report(self, filters, limit, user):
		params = json.loads(self.json)
		columns = self.get_standard_report_columns(params)
		result = []
		order_by, group_by, group_by_args = self.get_standard_report_order_by(params)

		_result = frappe.get_list(
			self.ref_doctype,
			fields=[
				get_group_by_field(group_by_args, c[1])
				if c[0] == "_aggregate_column" and group_by_args
				else Report._format([c[1], c[0]])
				for c in columns
			],
			filters=self.get_standard_report_filters(params, filters),
			order_by=order_by,
			group_by=group_by,
			as_list=True,
			limit=limit,
			user=user,
		)

		columns = self.build_standard_report_columns(columns, group_by_args)

		result = result + [list(d) for d in _result]

		if params.get("add_totals_row"):
			result = append_totals_row(result)

		return columns, result

	@staticmethod
	def _format(parts):
		# sort by is saved as DocType.fieldname, covert it to sql
		return "`tab{0}`.`{1}`".format(*parts)

	def get_standard_report_columns(self, params):
		if params.get("fields"):
			columns = params.get("fields")
		elif params.get("columns"):
			columns = params.get("columns")
		elif params.get("fields"):
			columns = params.get("fields")
		else:
			columns = [["name", self.ref_doctype]]
			for df in frappe.get_meta(self.ref_doctype).fields:
				if df.in_list_view:
					columns.append([df.fieldname, self.ref_doctype])

		return columns

	def get_standard_report_filters(self, params, filters):
		_filters = params.get("filters") or []

		if filters:
			for key, value in iteritems(filters):
				condition, _value = "=", value
				if isinstance(value, (list, tuple)):
					condition, _value = value
				_filters.append([key, condition, _value])

		return _filters

	def get_standard_report_order_by(self, params):
		group_by_args = None
		if params.get("sort_by"):
			order_by = Report._format(params.get("sort_by").split(".")) + " " + params.get("sort_order")

		elif params.get("order_by"):
			order_by = params.get("order_by")
		else:
			order_by = Report._format([self.ref_doctype, "modified"]) + " desc"

		if params.get("sort_by_next"):
			order_by += (
				", "
				+ Report._format(params.get("sort_by_next").split("."))
				+ " "
				+ params.get("sort_order_next")
			)

		group_by = None
		if params.get("group_by"):
			group_by_args = frappe._dict(params["group_by"])
			group_by = group_by_args["group_by"]
			order_by = "_aggregate_column desc"

		return order_by, group_by, group_by_args

	def build_standard_report_columns(self, columns, group_by_args):
		_columns = []

		for (fieldname, doctype) in columns:
			meta = frappe.get_meta(doctype)

			if meta.get_field(fieldname):
				field = meta.get_field(fieldname)
			else:
				if fieldname == "_aggregate_column":
					label = get_group_by_column_label(group_by_args, meta)
				else:
					label = meta.get_label(fieldname)

				field = frappe._dict(fieldname=fieldname, label=label)

				# since name is the primary key for a document, it will always be a Link datatype
				if fieldname == "name":
					field.fieldtype = "Link"
					field.options = doctype

			_columns.append(field)
		return _columns

	def build_data_dict(self, result, columns):
		data = []
		for row in result:
			if isinstance(row, (list, tuple)):
				_row = frappe._dict()
				for i, val in enumerate(row):
					_row[columns[i].get("fieldname")] = val
			elif isinstance(row, dict):
				# no need to convert from dict to dict
				_row = frappe._dict(row)
			data.append(_row)

		return data

	@frappe.whitelist()
	def toggle_disable(self, disable):
		if not self.has_permission("write"):
			frappe.throw(_("You are not allowed to edit the report."))

		self.db_set("disabled", cint(disable))


@frappe.whitelist()
def is_prepared_report_disabled(report):
	return frappe.db.get_value("Report", report, "disable_prepared_report") or 0


def get_report_module_dotted_path(module, report_name):
	return (
		frappe.local.module_app[scrub(module)]
		+ "."
		+ scrub(module)
		+ ".report."
		+ scrub(report_name)
		+ "."
		+ scrub(report_name)
	)


def get_group_by_field(args, doctype):
	if args["aggregate_function"] == "count":
		group_by_field = "count(*) as _aggregate_column"
	else:
		group_by_field = "{0}({1}) as _aggregate_column".format(
			args.aggregate_function, args.aggregate_on
		)

	return group_by_field


def get_group_by_column_label(args, meta):
	if args["aggregate_function"] == "count":
		label = "Count"
	else:
		sql_fn_map = {"avg": "Average", "sum": "Sum"}
		aggregate_on_label = meta.get_label(args.aggregate_on)
		label = _("{function} of {fieldlabel}").format(
			function=sql_fn_map[args.aggregate_function], fieldlabel=aggregate_on_label
		)
	return label
