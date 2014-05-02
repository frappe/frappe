# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""build query for doclistview and return results"""

import frappe, json
import frappe.defaults
import frappe.permissions
from frappe.utils import flt
from frappe import _

class DatabaseQuery(object):
	def __init__(self, doctype):
		self.doctype = doctype
		self.tables = []
		self.conditions = []
		self.ignore_permissions = False
		self.fields = ["name"]

	def execute(self, query=None, filters=None, fields=None, docstatus=None,
		group_by=None, order_by=None, limit_start=0, limit_page_length=20,
		as_list=False, with_childnames=False, debug=False, ignore_permissions=False):
		if not frappe.has_permission(self.doctype, "read"):
			raise frappe.PermissionError

		if fields:
			self.fields = fields
		self.filters = filters or []
		self.docstatus = docstatus or []
		self.group_by = group_by
		self.order_by = order_by
		self.limit_start = limit_start
		self.limit_page_length = limit_page_length
		self.with_childnames = with_childnames
		self.debug = debug
		self.as_list = as_list
		self.ignore_permissions = ignore_permissions


		if query:
			return self.run_custom_query(query)
		else:
			return self.build_and_run()

	def build_and_run(self):
		args = self.prepare_args()
		args.limit = self.add_limit()

		query = """select %(fields)s from %(tables)s where %(conditions)s
			%(group_by)s order by %(order_by)s %(limit)s""" % args

		return frappe.db.sql(query, as_dict=not self.as_list, debug=self.debug)

	def prepare_args(self):
		self.parse_args()
		self.extract_tables()
		self.remove_user_tags()
		self.build_conditions()

		args = frappe._dict()

		if self.with_childnames:
			for t in self.tables:
				if t != "`tab" + self.doctype + "`":
					self.fields.append(t + ".name as '%s:name'" % t[4:-1])

		# query dict
		args.tables = ', '.join(self.tables)
		args.conditions = ' and '.join(self.conditions)
		args.fields = ', '.join(self.fields)

		args.order_by = self.order_by or self.tables[0] + '.modified desc'
		args.group_by = self.group_by and (" group by " + self.group_by) or ""

		self.check_sort_by_table(args.order_by)

		return args


	def parse_args(self):
		if isinstance(self.filters, basestring):
			self.filters = json.loads(self.filters)
		if isinstance(self.fields, basestring):
			self.filters = json.loads(self.fields)
		if isinstance(self.filters, dict):
			fdict = self.filters
			self.filters = []
			for key, value in fdict.iteritems():
				self.filters.append(self.make_filter_tuple(key, value))

	def make_filter_tuple(self, key, value):
		if isinstance(value, (list, tuple)):
			return [self.doctype, key, value[0], value[1]]
		else:
			return [self.doctype, key, "=", value]

	def extract_tables(self):
		"""extract tables from fields"""
		self.tables = ['`tab' + self.doctype + '`']

		# add tables from fields
		if self.fields:
			for f in self.fields:
				if "." not in f: continue

				table_name = f.split('.')[0]
				if table_name.lower().startswith('group_concat('):
					table_name = table_name[13:]
				if table_name.lower().startswith('ifnull('):
					table_name = table_name[7:]
				if not table_name[0]=='`':
					table_name = '`' + table_name + '`'
				if not table_name in self.tables:
					self.append_table(table_name)

	def append_table(self, table_name):
		self.tables.append(table_name)
		doctype = table_name[4:-1]
		if (not self.ignore_permissions) and (not frappe.has_permission(doctype)):
			raise frappe.PermissionError, doctype

	def remove_user_tags(self):
		"""remove column _user_tags if not in table"""
		columns = frappe.db.get_table_columns(self.doctype)
		to_remove = []
		for fld in self.fields:
			for f in ("_user_tags", "_comments"):
				if f in fld and not f in columns:
					to_remove.append(fld)

		for fld in to_remove:
			del self.fields[self.fields.index(fld)]

	def build_conditions(self):
		self.conditions = []
		self.add_docstatus_conditions()
		self.build_filter_conditions()

		# join parent, child tables
		for tname in self.tables[1:]:
			self.conditions.append(tname + '.parent = ' + self.tables[0] + '.name')

		# match conditions
		if not self.ignore_permissions:
			match_conditions = self.build_match_conditions()
			if match_conditions:
				self.conditions.append(match_conditions)

	def add_docstatus_conditions(self):
		if self.docstatus:
			self.conditions.append(self.tables[0] + '.docstatus in (' + ','.join(self.docstatus) + ')')
		else:
			self.conditions.append(self.tables[0] + '.docstatus < 2')

	def build_filter_conditions(self):
		"""build conditions from user filters"""
		for f in self.filters:
			if isinstance(f, basestring):
				self.conditions.append(f)
			else:
				f = self.get_filter_tuple(f)

				tname = ('`tab' + f[0] + '`')
				if not tname in self.tables:
					self.append_table(tname)

				# prepare in condition
				if f[2] in ['in', 'not in']:
					opts = f[3]
					if not isinstance(opts, (list, tuple)):
						opts = f[3].split(",")
					opts = ["'" + t.strip().replace("'", "\\'") + "'" for t in opts]
					f[3] = "(" + ', '.join(opts) + ")"
					self.conditions.append('ifnull(' + tname + '.' + f[1] + ", '') " + f[2] + " " + f[3])
				else:
					df = frappe.get_meta(f[0]).get("fields", {"fieldname": f[1]})

					if f[2] == "like" or (isinstance(f[3], basestring) and
						(not df or df[0].fieldtype not in ["Float", "Int", "Currency", "Percent"])):
							value, default_val = ("'" + f[3].replace("'", "\\'") + "'"), '""'
					else:
						value, default_val = flt(f[3]), 0

					self.conditions.append('ifnull({tname}.{fname}, {default_val}) {operator} {value}'.format(
						tname=tname, fname=f[1], default_val=default_val, operator=f[2],
						value=value))

	def get_filter_tuple(self, f):
		if isinstance(f, dict):
			key, value = f.items()[0]
			f = self.make_filter_tuple(key, value)

		if not isinstance(f, (list, tuple)):
			frappe.throw("Filter must be a tuple or list (in a list)")

		if len(f) != 4:
			frappe.throw("Filter must have 4 values (doctype, fieldname, condition, value): " + str(f))

		return f

	def build_match_conditions(self, as_condition=True):
		"""add match conditions if applicable"""
		self.match_filters = {}
		self.match_conditions = []
		self.or_conditions = []

		if not self.tables: self.extract_tables()

		# explict permissions
		restricted_by_user = frappe.permissions.get_user_perms(frappe.get_meta(self.doctype)).restricted

		# get restrictions
		restrictions = frappe.defaults.get_restrictions()

		if restricted_by_user:
			self.or_conditions.append('`tab{doctype}`.`owner`="{user}"'.format(doctype=self.doctype,
				user=frappe.local.session.user))
			self.match_filters["owner"] = frappe.session.user

		if restrictions:
			self.add_restrictions(restrictions)

		if as_condition:
			return self.build_match_condition_string()
		else:
			return self.match_filters

	def add_restrictions(self, restrictions):
		fields_to_check = frappe.get_meta(self.doctype).get_restricted_fields(restrictions.keys())
		if self.doctype in restrictions:
			fields_to_check.append(frappe._dict({"fieldname":"name", "options":self.doctype}))

		# check in links
		for df in fields_to_check:
			self.match_conditions.append("""(ifnull(`tab{doctype}`.`{fieldname}`, "")="" or \
				`tab{doctype}`.`{fieldname}` in ({values}))""".format(doctype=self.doctype,
					fieldname=df.fieldname,
					values=", ".join([('"'+v.replace('"', '\"')+'"') \
						for v in restrictions[df.options]])))
			self.match_filters.setdefault(df.fieldname, [])
			self.match_filters[df.fieldname]= restrictions[df.options]

	def build_match_condition_string(self):
		conditions = " and ".join(self.match_conditions)
		doctype_conditions = self.get_permission_query_conditions()
		if doctype_conditions:
			conditions += ' and ' + doctype_conditions if conditions else doctype_conditions

		if self.or_conditions:
			if conditions:
				conditions = '({conditions}) or {or_conditions}'.format(conditions=conditions,
					or_conditions = ' or '.join(self.or_conditions))
			else:
				conditions = " or ".join(self.or_conditions)

		return conditions

	def get_permission_query_conditions(self):
		condition_methods = frappe.get_hooks("permission_query_conditions", {}).get(self.doctype, [])
		if condition_methods:
			conditions = []
			for method in condition_methods:
				c = frappe.get_attr(method)()
				if c:
					conditions.append(c)

			return " and ".join(conditions) if conditions else None

	def run_custom_query(self, query):
		if '%(key)s' in query:
			query = query.replace('%(key)s', 'name')
		return frappe.db.sql(query, as_dict = (not self.as_list))

	def check_sort_by_table(self, order_by):
		if "." in order_by:
			tbl = order_by.split('.')[0]
			if tbl not in self.tables:
				if tbl.startswith('`'):
					tbl = tbl[4:-1]
				frappe.throw(_("Please select atleast 1 column from {0} to sort").format(tbl))

	def add_limit(self):
		if self.limit_page_length:
			return 'limit %s, %s' % (self.limit_start, self.limit_page_length)
		else:
			return ''
