# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

import webnotes

form = webnotes.form
session = webnotes.session
sql = webnotes.conn.sql
out = webnotes.response

from webnotes.utils import cint


# Get, scrub metadata
# ====================================================================

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
	if sql('select name from `tabDocType` where istable=1 and name="%s"' % dt):
		import webnotes.model.meta
		return webnotes.model.meta.get_parent_dt(dt)
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
		res = sql("select fieldname, label, fieldtype, options, width from tabDocField where parent='%s'" % dt)
		for r in res:
			if r[0]:
				meta[dt][r[0]] = (r[1], r[2], r[3], r[4]);

		# name
		meta[dt]['name'] = ('ID', 'Link', dt, '200')

	return meta

# Additional conditions to fulfill match permission rules
# ====================================================================

def getmatchcondition(dt, ud, ur):
	res = sql("SELECT `role`, `match` FROM tabDocPerm WHERE parent = '%s' AND (`read`=1) AND permlevel = 0" % dt)
	cond = []
	for r in res:
		if r[0] in ur: # role applicable to user
			if r[1]:
				defvalues = ud.get(r[1],['_NA'])
				for d in defvalues:
					cond.append('`tab%s`.`%s`="%s"' % (dt, r[1], d))
			else: # nomatch i.e. full read rights
				return ''

	return ' OR '.join(cond)

def add_match_conditions(q, tl, ur, ud):
	sl = []
	for dt in tl:
		s = getmatchcondition(dt, ud, ur)
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

# execute server-side script from Search Criteria
# ====================================================================

def exec_report(code, res, colnames=[], colwidths=[], coltypes=[], coloptions=[], filter_values={}, query='', from_export=0):
	col_idx, i, out, style, header_html, footer_html, page_template = {}, 0, None, [], '', '', ''
	for c in colnames:
		col_idx[c] = i
		i+=1

	# load globals (api)
	from webnotes import *
	from webnotes.utils import *
	from webnotes.model.doc import *
	from webnotes.model.doclist import getlist
	from webnotes.model.db_schema import updatedb
	from webnotes.model.code import get_obj

	set = webnotes.conn.set
	sql = webnotes.conn.sql
	get_value = webnotes.conn.get_value
	convert_to_lists = webnotes.conn.convert_to_lists
	NEWLINE = '\n'

	exec str(code)

	if out!=None:
		res = out

	return res, style, header_html, footer_html, page_template

# ====================================================================

def guess_type(m):
	"""
		Returns fieldtype depending on the MySQLdb Description
	"""
	import MySQLdb
	if m in MySQLdb.NUMBER:
		return 'Currency'
	elif m in MySQLdb.DATE:
		return 'Date'
	else:
		return 'Data'

def build_description_simple():
	colnames, coltypes, coloptions, colwidths = [], [], [], []

	for m in webnotes.conn.get_description():
		colnames.append(m[0])
		coltypes.append(guess_type[m[0]])
		coloptions.append('')
		colwidths.append('100')

	return colnames, coltypes, coloptions, colwidths

# ====================================================================

def build_description_standard(meta, tl):

	desc = webnotes.conn.get_description()

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

		elif meta.get(dt,{}).has_key(fn):
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

# Entry Point - Run the query
# ====================================================================

@webnotes.whitelist(allow_guest=True)
def runquery(q='', ret=0, from_export=0):
	import webnotes.utils

	formatted = cint(form.getvalue('formatted'))

	# CASE A: Simple Query
	# --------------------
	if form.getvalue('simple_query') or form.getvalue('is_simple'):
		if not q: q = form.getvalue('simple_query') or form.getvalue('query')
		if q.split()[0].lower() != 'select':
			raise Exception, 'Query must be a SELECT'

		as_dict = cint(form.getvalue('as_dict'))
		res = sql(q, as_dict = as_dict, as_list = not as_dict, formatted=formatted)

		# build colnames etc from metadata
		colnames, coltypes, coloptions, colwidths = [], [], [], []

	# CASE B: Standard Query
	# -----------------------
	else:
		if not q: q = form.getvalue('query')

		tl = get_sql_tables(q)
		meta = get_sql_meta(tl)

		q = add_match_conditions(q, tl, webnotes.user.roles, webnotes.user.get_defaults())
		webnotes
		# replace special variables
		q = q.replace('__user', session['user'].encode('utf-8'))
		q = q.replace('__today', webnotes.utils.nowdate())

		res = sql(q, as_list=1, formatted=formatted)

		colnames, coltypes, coloptions, colwidths = build_description_standard(meta, tl)

	# run server script
	# -----------------
	style, header_html, footer_html, page_template = '', '', '', ''
	if form.has_key('sc_id') and form.getvalue('sc_id'):
		sc_id = form.getvalue('sc_id')
		from webnotes.model.code import get_code
		sc_details = webnotes.conn.sql("select module, standard, server_script from `tabSearch Criteria` where name=%s", sc_id)[0]
		if sc_details[1]!='No':
			code = get_code(sc_details[0], 'Search Criteria', sc_id, 'py')
		else:
			code = sc_details[2]

		if code:
			filter_values = form.has_key('filter_values') and eval(form.getvalue('filter_values','')) or {}
			res, style, header_html, footer_html, page_template = exec_report(code, res, colnames, colwidths, coltypes, coloptions, filter_values, q, from_export)

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
	qm = form.has_key('query_max') and form.getvalue('query_max') or ''
	if qm and qm.strip():
		if qm.split()[0].lower() != 'select':
			raise Exception, 'Query (Max) must be a SELECT'
		if not form.has_key('simple_query'):
			qm = add_match_conditions(qm, tl, webnotes.user.roles, webnotes.user.defaults)

		out['n_values'] = webnotes.utils.cint(sql(qm)[0][0])


@webnotes.whitelist()
def runquery_csv():
	global out

	# run query
	res = runquery(from_export = 1)

	q = form.getvalue('query')

	rep_name = form.getvalue('report_name')
	if not form.has_key('simple_query'):

		# Report Name
		if not rep_name:
			rep_name = get_sql_tables(q)[0]

	if not rep_name: rep_name = 'DataExport'

	# Headings
	heads = []

	rows = [[rep_name], out['colnames']] + out['values']

	from cStringIO import StringIO
	import csv

	f = StringIO()
	writer = csv.writer(f)
	for r in rows:
		for i in xrange(len(r)):
			if type(r[i]) is unicode:
				r[i] = r[i].encode('utf-8')
		writer.writerow(r)

	f.seek(0)
	out['result'] = f.read()
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
			
		import webnotes.utils
		args['limit_start'] = webnotes.utils.cint(args.get('limit_start'))
		args['limit_page_length'] = webnotes.utils.cint(args.get('limit_page_length'))
	
	return query, args