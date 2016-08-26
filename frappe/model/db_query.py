# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""build query for doclistview and return results"""

import frappe, json
import frappe.defaults
import frappe.share
import frappe.permissions
from frappe.utils import flt, cint, getdate, get_datetime, get_time, make_filter_tuple, get_filter
from frappe import _
from frappe.model import optional_fields
from frappe.model.utils.list_settings import get_list_settings, update_list_settings

class DatabaseQuery(object):
	def __init__(self, doctype):
		self.doctype = doctype
		self.tables = []
		self.conditions = []
		self.or_conditions = []
		self.fields = None
		self.user = None
		self.ignore_ifnull = False
		self.flags = frappe._dict()

	def execute(self, query=None, fields=None, filters=None, or_filters=None,
		docstatus=None, group_by=None, order_by=None, limit_start=False,
		limit_page_length=None, as_list=False, with_childnames=False, debug=False,
		ignore_permissions=False, user=None, with_comment_count=False,
		join='left join', distinct=False, start=None, page_length=None, limit=None,
		ignore_ifnull=False, save_list_settings=False, save_list_settings_fields=False,
		update=None):
		if not ignore_permissions and not frappe.has_permission(self.doctype, "read", user=user):
			raise frappe.PermissionError, self.doctype

		# fitlers and fields swappable
		# its hard to remember what comes first
		if (isinstance(fields, dict)
			or (isinstance(fields, list) and fields and isinstance(fields[0], list))):
			# if fields is given as dict/list of list, its probably filters
			filters, fields = fields, filters

		elif fields and isinstance(filters, list) \
			and len(filters) > 1 and isinstance(filters[0], basestring):
			# if `filters` is a list of strings, its probably fields
			filters, fields = fields, filters

		if fields:
			self.fields = fields
		else:
			self.fields =  ["`tab{0}`.`name`".format(self.doctype)]

		if start: limit_start = start
		if page_length: limit_page_length = page_length
		if limit: limit_page_length = limit

		self.filters = filters or []
		self.or_filters = or_filters or []
		self.docstatus = docstatus or []
		self.group_by = group_by
		self.order_by = order_by
		self.limit_start = 0 if (limit_start is False) else cint(limit_start)
		self.limit_page_length = cint(limit_page_length) if limit_page_length else None
		self.with_childnames = with_childnames
		self.debug = debug
		self.join = join
		self.distinct = distinct
		self.as_list = as_list
		self.ignore_ifnull = ignore_ifnull
		self.flags.ignore_permissions = ignore_permissions
		self.user = user or frappe.session.user
		self.update = update
		#self.debug = True

		if query:
			result = self.run_custom_query(query)
		else:
			result = self.build_and_run()

		if with_comment_count and not as_list and self.doctype:
			self.add_comment_count(result)

		if save_list_settings:
			self.save_list_settings_fields = save_list_settings_fields
			self.update_list_settings()

		return result

	def build_and_run(self):
		args = self.prepare_args()
		args.limit = self.add_limit()

		if args.conditions:
			args.conditions = "where " + args.conditions

		if self.distinct:
			args.fields = 'distinct ' + args.fields

		query = """select %(fields)s from %(tables)s %(conditions)s
			%(group_by)s %(order_by)s %(limit)s""" % args

		return frappe.db.sql(query, as_dict=not self.as_list, debug=self.debug, update=self.update)

	def prepare_args(self):
		self.parse_args()
		self.extract_tables()
		self.set_optional_columns()
		self.build_conditions()

		args = frappe._dict()

		if self.with_childnames:
			for t in self.tables:
				if t != "`tab" + self.doctype + "`":
					self.fields.append(t + ".name as '%s:name'" % t[4:-1])

		# query dict
		args.tables = self.tables[0]

		# left join parent, child tables
		for child in self.tables[1:]:
			args.tables += " {join} {child} on ({child}.parent = {main}.name)".format(join=self.join,
				child=child, main=self.tables[0])

		if self.grouped_or_conditions:
			self.conditions.append("({0})".format(" or ".join(self.grouped_or_conditions)))

		args.conditions = ' and '.join(self.conditions)

		if self.or_conditions:
			args.conditions += (' or ' if args.conditions else "") + \
				 ' or '.join(self.or_conditions)

		self.set_field_tables()

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
					filters.append(make_filter_tuple(self.doctype, key, value))
			setattr(self, filter_name, filters)

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

	def set_field_tables(self):
		'''If there are more than one table, the fieldname must not be ambigous.
		If the fieldname is not explicitly mentioned, set the default table'''
		if len(self.tables) > 1:
			for i, f in enumerate(self.fields):
				if '.' not in f:
					self.fields[i] = '{0}.{1}'.format(self.tables[0], f)

	def set_optional_columns(self):
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

		f = get_filter(self.doctype, f)

		tname = ('`tab' + f.doctype + '`')
		if not tname in self.tables:
			self.append_table(tname)

		column_name = '{tname}.{fname}'.format(tname=tname,
			fname=f.fieldname)

		can_be_null = True

		# prepare in condition
		if f.operator in ('in', 'not in'):
			values = f.value
			if not isinstance(values, (list, tuple)):
				values = values.split(",")

			fallback = "''"
			value = (frappe.db.escape((v or '').strip(), percent=False) for v in values)
			value = '("{0}")'.format('", "'.join(value))
		else:
			df = frappe.get_meta(f.doctype).get("fields", {"fieldname": f.fieldname})
			df = df[0] if df else None

			if df and df.fieldtype in ("Check", "Float", "Int", "Currency", "Percent"):
				can_be_null = False

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

					if f.operator in ("like", "not like") and isinstance(value, basestring):
						# because "like" uses backslash (\) for escaping
						value = value.replace("\\", "\\\\").replace("%", "%%")

			else:
				value = flt(f.value)
				fallback = 0

			# put it inside double quotes
			if isinstance(value, basestring):
				value = '"{0}"'.format(frappe.db.escape(value, percent=False))

		if (self.ignore_ifnull or not can_be_null
			or (f.value and f.operator in ('=', 'like')) or 'ifnull(' in column_name.lower()):
			condition = '{column_name} {operator} {value}'.format(
				column_name=column_name, operator=f.operator,
				value=value)
		else:
			condition = 'ifnull({column_name}, {fallback}) {operator} {value}'.format(
				column_name=column_name, fallback=fallback, operator=f.operator,
				value=value)

		return condition

	def build_match_conditions(self, as_condition=True):
		"""add match conditions if applicable"""
		self.match_filters = []
		self.match_conditions = []
		only_if_shared = False
		if not self.user:
			self.user = frappe.session.user

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
					frappe.db.escape(self.user, percent=False)))

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

			return conditions

		else:
			return self.match_filters

	def get_share_condition(self):
		return """`tab{0}`.name in ({1})""".format(self.doctype, ", ".join(["'%s'"] * len(self.shared))) % \
			tuple([frappe.db.escape(s, percent=False) for s in self.shared])

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
						values=", ".join([('"'+frappe.db.escape(v, percent=False)+'"') for v in user_permission_values])
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
				sort_field = sort_order = None
				if meta.sort_field and ',' in meta.sort_field:
					# multiple sort given in doctype definition
					# Example:
					# `idx desc, modified desc`
					# will covert to
					# `tabItem`.`idx` desc, `tabItem`.`modified` desc
					args.order_by = ', '.join(['`tab{0}`.`{1}` {2}'.format(self.doctype,
						f.split()[0].strip(), f.split()[1].strip()) for f in meta.sort_field.split(',')])
				else:
					sort_field = meta.sort_field or 'modified'
					sort_order = (meta.sort_field and meta.sort_order) or 'desc'

					args.order_by = "`tab{0}`.`{1}` {2}".format(self.doctype, sort_field or "modified", sort_order or "desc")

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

	def add_comment_count(self, result):
		for r in result:
			if not r.name:
				continue

			r._comment_count = 0
			if "_comments" in r:
				r._comment_count = len(json.loads(r._comments or "[]"))

	def update_list_settings(self):
		# update list settings if new search
		list_settings = json.loads(get_list_settings(self.doctype) or '{}')
		list_settings['filters'] = self.filters
		list_settings['limit'] = self.limit_page_length
		list_settings['order_by'] = self.order_by

		if self.save_list_settings_fields:
			list_settings['fields'] = self.fields

		update_list_settings(self.doctype, list_settings)

