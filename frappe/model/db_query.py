# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""build query for doclistview and return results"""

import frappe, json
import frappe.defaults
import frappe.share
import frappe.permissions
from frappe.utils import flt, cint, getdate, get_datetime, get_time
from frappe import _
from frappe.model import optional_fields

class DatabaseQuery(object):
	def __init__(self, doctype):
		self.doctype = doctype
		self.tables = []
		self.conditions = []
		self.or_conditions = []
		self.fields = ["`tab{0}`.`name`".format(doctype)]
		self.user = None
		self.flags = frappe._dict()

	def execute(self, query=None, fields=None, filters=None, or_filters=None,
		docstatus=None, group_by=None, order_by=None, limit_start=False,
		limit_page_length=None, as_list=False, with_childnames=False, debug=False,
		ignore_permissions=False, user=None):
		if not ignore_permissions and not frappe.has_permission(self.doctype, "read", user=user):
			raise frappe.PermissionError, self.doctype

		if fields:
			self.fields = fields
		self.filters = filters or []
		self.or_filters = or_filters or []
		self.docstatus = docstatus or []
		self.group_by = group_by
		self.order_by = order_by
		self.limit_start = 0 if (limit_start is False) else cint(limit_start)
		self.limit_page_length = cint(limit_page_length) if limit_page_length else None
		self.with_childnames = with_childnames
		self.debug = debug
		self.as_list = as_list
		self.flags.ignore_permissions = ignore_permissions
		self.user = user or frappe.session.user

		if query:
			return self.run_custom_query(query)
		else:
			return self.build_and_run()

	def build_and_run(self):
		args = self.prepare_args()
		args.limit = self.add_limit()

		if args.conditions:
			args.conditions = "where " + args.conditions

		query = """select %(fields)s from %(tables)s %(conditions)s
			%(group_by)s %(order_by)s %(limit)s""" % args

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
		args.tables = self.tables[0]

		# left join parent, child tables
		for tname in self.tables[1:]:
			args.tables += " left join " + tname + " on " + tname + '.parent = ' + self.tables[0] + '.name'

		if self.grouped_or_conditions:
			self.conditions.append("({0})".format(" or ".join(self.grouped_or_conditions)))

		args.conditions = ' and '.join(self.conditions)

		if self.or_conditions:
			args.conditions += (' or ' if args.conditions else "") + \
				 ' or '.join(self.or_conditions)

		args.fields = ', '.join(self.fields)

		self.set_order_by(args)
		self.check_sort_by_table(args.order_by)
		args.order_by = args.order_by and (" order by " + args.order_by) or ""

		args.group_by = self.group_by and (" group by " + self.group_by) or ""

		return args

	def parse_args(self):
		"""Convert fields and filters from strings to list, dicts"""
		if isinstance(self.fields, basestring):
			if self.fields == "*":
				self.fields = ["*"]
			else:
				try:
					self.fields = json.loads(self.fields)
				except ValueError:
					self.fields = [f.strip() for f in self.fields.split(",")]

		for filter_name in ["filters", "or_filters"]:
			filters = getattr(self, filter_name)
			if isinstance(filters, basestring):
				filters = json.loads(filters)

			if isinstance(filters, dict):
				fdict = filters
				filters = []
				for key, value in fdict.iteritems():
					filters.append(self.make_filter_tuple(key, value))
			setattr(self, filter_name, filters)

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
				if ( not ("tab" in f and "." in f) ) or ("locate(" in f): continue


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
		if (not self.flags.ignore_permissions) and (not frappe.has_permission(doctype)):
			raise frappe.PermissionError, doctype

	def remove_user_tags(self):
		"""Removes optional columns like `_user_tags`, `_comments` etc. if not in table"""
		columns = frappe.db.get_table_columns(self.doctype)

		# remove from fields
		to_remove = []
		for fld in self.fields:
			for f in optional_fields:
				if f in fld and not f in columns:
					to_remove.append(fld)

		for fld in to_remove:
			del self.fields[self.fields.index(fld)]

		# remove from filters
		to_remove = []
		for each in self.filters:
			if isinstance(each, basestring):
				each = [each]

			for element in each:
				if element in optional_fields and element not in columns:
					to_remove.append(each)

		for each in to_remove:
			if isinstance(self.filters, dict):
				del self.filters[each]
			else:
				self.filters.remove(each)

	def build_conditions(self):
		self.conditions = []
		self.grouped_or_conditions = []
		self.build_filter_conditions(self.filters, self.conditions)
		self.build_filter_conditions(self.or_filters, self.grouped_or_conditions)

		# match conditions
		if not self.flags.ignore_permissions:
			match_conditions = self.build_match_conditions()
			if match_conditions:
				self.conditions.append("(" + match_conditions + ")")

	def build_filter_conditions(self, filters, conditions):
		"""build conditions from user filters"""
		if isinstance(filters, dict):
			filters = [filters]

		for f in filters:
			if isinstance(f, basestring):
				conditions.append(f)
			else:
				conditions.append(self.prepare_filter_condition(f))

	def prepare_filter_condition(self, f):
		"""Returns a filter condition in the format:

				ifnull(`tabDocType`.`fieldname`, fallback) operator "value"
		"""

		f = self.get_filter(f)

		tname = ('`tab' + f.doctype + '`')
		if not tname in self.tables:
			self.append_table(tname)

		# prepare in condition
		if f.operator in ('in', 'not in'):
			values = f.value
			if not isinstance(values, (list, tuple)):
				values = values.split(",")

			values = (frappe.db.escape(v.strip()) for v in values)
			values = '("{0}")'.format('", "'.join(values))

			condition = 'ifnull({tname}.{fname}, "") {operator} {value}'.format(
				tname=tname, fname=f.fieldname, operator=f.operator, value=values)

		else:
			df = frappe.get_meta(f.doctype).get("fields", {"fieldname": f.fieldname})
			df = df[0] if df else None

			if df and df.fieldtype=="Date":
				value = getdate(f.value).strftime("%Y-%m-%d")
				fallback = "'0000-00-00'"

			elif df and df.fieldtype=="Datetime":
				value = get_datetime(f.value).strftime("%Y-%m-%d %H:%M:%S.%f")
				fallback = "'0000-00-00 00:00:00'"

			elif df and df.fieldtype=="Time":
				value = get_time(f.value).strftime("%H:%M:%S.%f")
				fallback = "'00:00:00'"

			elif f.operator in ("like", "not like") or (isinstance(f.value, basestring) and
				(not df or df.fieldtype not in ["Float", "Int", "Currency", "Percent", "Check"])):
					value = "" if f.value==None else f.value
					fallback = '""'

					if f.operator == "like" and isinstance(value, basestring):
						# because "like" uses backslash (\) for escaping
						value = value.replace("\\", "\\\\")

			else:
				value = flt(f.value)
				fallback = 0

			# put it inside double quotes
			if isinstance(value, basestring):
				value = '"{0}"'.format(frappe.db.escape(value))

			condition = 'ifnull({tname}.{fname}, {fallback}) {operator} {value}'.format(
				tname=tname, fname=f.fieldname, fallback=fallback, operator=f.operator,
				value=value)

		# replace % with %% to prevent python format string error
		return condition.replace("%", "%%")

	def get_filter(self, f):
		"""Returns a _dict like

			{
				"doctype": "DocType",
				"fieldname": "fieldname",
				"operator": "=",
				"value": "value"
			}

		"""
		if isinstance(f, dict):
			key, value = f.items()[0]
			f = self.make_filter_tuple(key, value)

		if not isinstance(f, (list, tuple)):
			frappe.throw("Filter must be a tuple or list (in a list)")

		if len(f) == 3:
			f = (self.doctype, f[0], f[1], f[2])

		elif len(f) != 4:
			frappe.throw("Filter must have 4 values (doctype, fieldname, operator, value): {0}".format(str(f)))

		if not f[2]:
			# if operator is missing
			f[2] = "="

		valid_operators = ("=", "!=", ">", "<", ">=", "<=", "like", "not like", "in", "not in")
		if f[2] not in valid_operators:
			frappe.throw("Operator must be one of {0}".format(", ".join(valid_operators)))

		return frappe._dict({
			"doctype": f[0],
			"fieldname": f[1],
			"operator": f[2],
			"value": f[3]
		})

	def build_match_conditions(self, as_condition=True):
		"""add match conditions if applicable"""
		self.match_filters = []
		self.match_conditions = []
		only_if_shared = False

		if not self.tables: self.extract_tables()

		meta = frappe.get_meta(self.doctype)
		role_permissions = frappe.permissions.get_role_permissions(meta, user=self.user)

		self.shared = frappe.share.get_shared(self.doctype, self.user)

		if not meta.istable and not role_permissions.get("read") and not self.flags.ignore_permissions:
			only_if_shared = True
			if not self.shared:
				frappe.throw(_("No permission to read {0}").format(self.doctype), frappe.PermissionError)
			else:
				self.conditions.append(self.get_share_condition())

		else:
			# apply user permissions?
			if role_permissions.get("apply_user_permissions", {}).get("read"):
				# get user permissions
				user_permissions = frappe.defaults.get_user_permissions(self.user)
				self.add_user_permissions(user_permissions,
					user_permission_doctypes=role_permissions.get("user_permission_doctypes").get("read"))

			if role_permissions.get("if_owner", {}).get("read"):
				self.match_conditions.append("`tab{0}`.owner = '{1}'".format(self.doctype,
					frappe.db.escape(frappe.session.user)))

		if as_condition:
			conditions = ""
			if self.match_conditions:
				# will turn out like ((blog_post in (..) and blogger in (...)) or (blog_category in (...)))
				conditions = "((" + ") or (".join(self.match_conditions) + "))"

			doctype_conditions = self.get_permission_query_conditions()
			if doctype_conditions:
				conditions += (' and ' + doctype_conditions) if conditions else doctype_conditions

			# share is an OR condition, if there is a role permission
			if not only_if_shared and self.shared and conditions:
				conditions =  "({conditions}) or ({shared_condition})".format(
					conditions=conditions, shared_condition=self.get_share_condition())

			# replace % with %% to prevent python format string error
			return conditions.replace("%", "%%")

		else:
			return self.match_filters

	def get_share_condition(self):
		return """`tab{0}`.name in ({1})""".format(self.doctype, ", ".join(["'%s'"] * len(self.shared))) % \
			tuple([frappe.db.escape(s) for s in self.shared])

	def add_user_permissions(self, user_permissions, user_permission_doctypes=None):
		user_permission_doctypes = frappe.permissions.get_user_permission_doctypes(user_permission_doctypes, user_permissions)
		meta = frappe.get_meta(self.doctype)

		for doctypes in user_permission_doctypes:
			match_filters = {}
			match_conditions = []
			# check in links
			for df in meta.get_fields_to_check_permissions(doctypes):
				user_permission_values = user_permissions.get(df.options, [])

				condition = 'ifnull(`tab{doctype}`.`{fieldname}`, "")=""'.format(doctype=self.doctype, fieldname=df.fieldname)
				if user_permission_values:
					condition += """ or `tab{doctype}`.`{fieldname}` in ({values})""".format(
						doctype=self.doctype, fieldname=df.fieldname,
						values=", ".join([('"'+frappe.db.escape(v)+'"') for v in user_permission_values])
					)
				match_conditions.append("({condition})".format(condition=condition))

				match_filters[df.options] = user_permission_values

			if match_conditions:
				self.match_conditions.append(" and ".join(match_conditions))

			if match_filters:
				self.match_filters.append(match_filters)

	def get_permission_query_conditions(self):
		condition_methods = frappe.get_hooks("permission_query_conditions", {}).get(self.doctype, [])
		if condition_methods:
			conditions = []
			for method in condition_methods:
				c = frappe.call(frappe.get_attr(method), self.user)
				if c:
					conditions.append(c)

			return " and ".join(conditions) if conditions else None

	def run_custom_query(self, query):
		if '%(key)s' in query:
			query = query.replace('%(key)s', 'name')
		return frappe.db.sql(query, as_dict = (not self.as_list))

	def set_order_by(self, args):
		meta = frappe.get_meta(self.doctype)
		if self.order_by:
			args.order_by = self.order_by
		else:
			args.order_by = ""

			# don't add order by from meta if a mysql group function is used without group by clause
			group_function_without_group_by = (len(self.fields)==1 and
				(	self.fields[0].lower().startswith("count(")
					or self.fields[0].lower().startswith("min(")
					or self.fields[0].lower().startswith("max(")
				) and not self.group_by)

			if not group_function_without_group_by:
				args.order_by = "`tab{0}`.`{1}` {2}".format(self.doctype,
					meta.get("sort_field") or "modified", meta.get("sort_order") or "desc")

				# draft docs always on top
				if meta.is_submittable:
					args.order_by = "`tab{0}`.docstatus asc, {1}".format(self.doctype, args.order_by)

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
