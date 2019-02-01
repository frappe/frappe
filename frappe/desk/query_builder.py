# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

out = frappe.response

from frappe.utils import cint
import frappe.defaults
from six import text_type

# imports - third-party imports
import pymysql

def get_sql_tables(q):
	if q.find('WHERE') != -1:
		tl = q.split('FROM')[1].split('WHERE')[0].split(',')
	elif q.find('GROUP BY') != -1:
		tl = q.split('FROM')[1].split('GROUP BY')[0].split(',')
	else:
		tl = q.split('FROM')[1].split('ORDER BY')[0].split(',')
	return [t.strip().strip('`')[3:] for t in tl]

def get_parent_dt(dt):
	pdt = ''
	if frappe.db.sql('select name from `tabDocType` where istable=1 and name=%s', dt):
		import frappe.model.meta
		return frappe.model.meta.get_parent_dt(dt)
	return pdt

def get_sql_meta(tl):
	std_columns = {
		'owner':('Owner', '', '', '100'),
		'creation':('Created on', 'Date', '', '100'),
		'modified':('Last modified on', 'Date', '', '100'),
		'modified_by':('Modified By', '', '', '100')
	}

	meta = {}

	for dt in tl:
		meta[dt] = std_columns.copy()

		# for table doctype, the ID is the parent id
		pdt = get_parent_dt(dt)
		if pdt:
			meta[dt]['parent'] = ('ID', 'Link', pdt, '200')

		# get the field properties from DocField
		res = frappe.db.sql("select fieldname, label, fieldtype, options, width \
			from tabDocField where parent=%s", dt)
		for r in res:
			if r[0]:
				meta[dt][r[0]] = (r[1], r[2], r[3], r[4]);

		# name
		meta[dt]['name'] = ('ID', 'Link', dt, '200')

	return meta

def add_match_conditions(q, tl):
	from frappe.desk.reportview import build_match_conditions
	sl = []
	for dt in tl:
		s = build_match_conditions(dt)
		if s:
			sl.append(s)

	# insert the conditions
	if sl:
		condition_st  = q.find('WHERE')!=-1 and ' AND ' or ' WHERE '
		condition_end = q.find('ORDER BY')!=-1 and 'ORDER BY' or 'LIMIT'
		condition_end = q.find('GROUP BY')!=-1 and 'GROUP BY' or condition_end

		if q.find('ORDER BY')!=-1 or q.find('LIMIT')!=-1 or q.find('GROUP BY')!=-1: # if query continues beyond conditions
			q = q.split(condition_end)
			q = q[0] + condition_st + '(' + ' OR '.join(sl) + ') ' + condition_end + q[1]
		else:
			q = q + condition_st + '(' + ' OR '.join(sl) + ')'

	return q

def guess_type(m):
	"""
		Returns fieldtype depending on the MySQLdb Description
	"""
	if m in pymysql.NUMBER:
		return 'Currency'
	elif m in pymysql.DATE:
		return 'Date'
	else:
		return 'Data'

def build_description_simple():
	colnames, coltypes, coloptions, colwidths = [], [], [], []

	for m in frappe.db.get_description():
		colnames.append(m[0])
		coltypes.append(guess_type[m[0]])
		coloptions.append('')
		colwidths.append('100')

	return colnames, coltypes, coloptions, colwidths

def build_description_standard(meta, tl):

	desc = frappe.db.get_description()

	colnames, coltypes, coloptions, colwidths = [], [], [], []

	# merged metadata - used if we are unable to
	# get both the table name and field name from
	# the description - in case of joins
	merged_meta = {}
	for d in meta:
		merged_meta.update(meta[d])

	for f in desc:
		fn, dt = f[0], ''
		if '.' in fn:
			dt, fn = fn.split('.')

		if (not dt) and merged_meta.get(fn):
			# no "AS" given, find type from merged description

			desc = merged_meta[fn]
			colnames.append(desc[0] or fn)
			coltypes.append(desc[1] or '')
			coloptions.append(desc[2] or '')
			colwidths.append(desc[3] or '100')

		elif fn in meta.get(dt,{}):
			# type specified for a multi-table join
			# usually from Report Builder

			desc = meta[dt][fn]
			colnames.append(desc[0] or fn)
			coltypes.append(desc[1] or '')
			coloptions.append(desc[2] or '')
			colwidths.append(desc[3] or '100')

		else:
			# nothing found
			# guess
			colnames.append(fn)
			coltypes.append(guess_type(f[1]))
			coloptions.append('')
			colwidths.append('100')

	return colnames, coltypes, coloptions, colwidths

@frappe.whitelist()
def runquery(q='', ret=0, from_export=0):
	import frappe.utils

	formatted = cint(frappe.form_dict.get('formatted'))

	# CASE A: Simple Query
	# --------------------
	if frappe.form_dict.get('simple_query') or frappe.form_dict.get('is_simple'):
		if not q: q = frappe.form_dict.get('simple_query') or frappe.form_dict.get('query')
		if q.split()[0].lower() != 'select':
			raise Exception('Query must be a SELECT')

		as_dict = cint(frappe.form_dict.get('as_dict'))
		res = frappe.db.sql(q, as_dict = as_dict, as_list = not as_dict, formatted=formatted)

		# build colnames etc from metadata
		colnames, coltypes, coloptions, colwidths = [], [], [], []

	# CASE B: Standard Query
	# -----------------------
	else:
		if not q: q = frappe.form_dict.get('query')

		tl = get_sql_tables(q)
		meta = get_sql_meta(tl)

		q = add_match_conditions(q, tl)

		# replace special variables
		q = q.replace('__user', frappe.session.user)
		q = q.replace('__today', frappe.utils.nowdate())

		res = frappe.db.sql(q, as_list=1, formatted=formatted)

		colnames, coltypes, coloptions, colwidths = build_description_standard(meta, tl)

	# run server script
	# -----------------
	style, header_html, footer_html, page_template = '', '', '', ''

	out['colnames'] = colnames
	out['coltypes'] = coltypes
	out['coloptions'] = coloptions
	out['colwidths'] = colwidths
	out['header_html'] = header_html
	out['footer_html'] = footer_html
	out['page_template'] = page_template

	if style:
		out['style'] = style

	# just the data - return
	if ret==1:
		return res

	out['values'] = res

	# return num of entries
	qm = frappe.form_dict.get('query_max') or ''
	if qm and qm.strip():
		if qm.split()[0].lower() != 'select':
			raise Exception('Query (Max) must be a SELECT')
		if not frappe.form_dict.get('simple_query'):
			qm = add_match_conditions(qm, tl)

		out['n_values'] = frappe.utils.cint(frappe.db.sql(qm)[0][0])


@frappe.whitelist()
def runquery_csv():
	global out

	q = frappe.form_dict.get('query')

	rep_name = frappe.form_dict.get('report_name')
	if not frappe.form_dict.get('simple_query'):

		# Report Name
		if not rep_name:
			rep_name = get_sql_tables(q)[0]

	if not rep_name: rep_name = 'DataExport'

	rows = [[rep_name], out['colnames']] + out['values']

	from six import StringIO
	import csv

	f = StringIO()
	writer = csv.writer(f)
	for r in rows:
		# encode only unicode type strings and not int, floats etc.
		writer.writerow(map(lambda v: isinstance(v, text_type) and v.encode('utf-8') or v, r))

	f.seek(0)
	out['result'] = text_type(f.read(), 'utf-8')
	out['type'] = 'csv'
	out['doctype'] = rep_name

def add_limit_to_query(query, args):
	"""
		Add limit condition to query
		can be used by methods called in listing to add limit condition
	"""
	if args.get('limit_page_length'):
		query += """
			limit %(limit_start)s, %(limit_page_length)s"""

		import frappe.utils
		args['limit_start'] = frappe.utils.cint(args.get('limit_start'))
		args['limit_page_length'] = frappe.utils.cint(args.get('limit_page_length'))

	return query, args
