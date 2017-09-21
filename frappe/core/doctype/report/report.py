# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _
import frappe.desk.query_report
from frappe.utils import cint
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files
from frappe.modules import make_boilerplate
from frappe.core.doctype.page.page import delete_custom_role
from frappe.core.doctype.custom_role.custom_role import get_custom_allowed_roles
from six import iteritems


class Report(Document):
	def validate(self):
		"""only administrator can save standard report"""
		if not self.module:
			self.module = frappe.db.get_value("DocType", self.ref_doctype, "module")

		if not self.is_standard:
			self.is_standard = "No"
			if frappe.session.user=="Administrator" and getattr(frappe.local.conf, 'developer_mode',0)==1:
				self.is_standard = "Yes"

		if self.is_standard == "No" and frappe.db.get_value("Report", self.name, "is_standard") == "Yes":
			frappe.throw(_("Cannot edit a standard report. Please duplicate and create a new report"))

		if self.is_standard == "Yes" and frappe.session.user!="Administrator":
			frappe.throw(_("Only Administrator can save a standard report. Please rename and save."))

		if self.report_type in ("Query Report", "Script Report") \
			and frappe.session.user!="Administrator":
			frappe.throw(_("Only Administrator allowed to create Query / Script Reports"))

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

		roles = frappe.get_roles()

		if has_common(roles, allowed):
			return True

	def update_report_json(self):
		if self.json:
			data = json.loads(self.json)
			data["add_total_row"] = self.add_total_row
			self.json = json.dumps(data)

	def export_doc(self):
		if frappe.flags.in_import:
			return

		if self.is_standard == 'Yes' and (frappe.local.conf.get('developer_mode') or 0) == 1:
			export_to_files(record_list=[['Report', self.name]],
				record_module=self.module)

			self.create_report_py()

	def create_report_py(self):
		if self.report_type == "Script Report":
			make_boilerplate("controller.py", self, {"name": self.name})
			make_boilerplate("controller.js", self, {"name": self.name})

	def get_data(self, filters=None, limit=None, user=None, as_dict=False):
		columns = []
		out = []

		if self.report_type in ('Query Report', 'Script Report'):
			# query and script reports
			data = frappe.desk.query_report.run(self.name, filters=filters, user=user)
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

					columns.append(frappe._dict(label=parts[0], fieldtype=fieldtype, fieldname=parts[0]))

			out += data.get('result')
		else:
			# standard report
			params = json.loads(self.json)
			columns = params.get('columns')
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

			order_by = _format(params.get('sort_by').split('.')) + ' ' + params.get('sort_order')
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
			for column in columns:
				meta = frappe.get_meta(column[1])
				field = [meta.get_field(column[0]) or frappe._dict(label=meta.get_label(column[0]), fieldname=column[0])]
				_columns.extend(field)
			columns = _columns

			out = out + [list(d) for d in result]

		if as_dict:
			data = []
			for row in out:
				_row = frappe._dict()
				data.append(_row)
				for i, val in enumerate(row):
					_row[columns[i].get('fieldname')] = val
		else:
			data = out
		return columns, data


	@Document.whitelist
	def toggle_disable(self, disable):
		self.db_set("disabled", cint(disable))
