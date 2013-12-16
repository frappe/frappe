# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""build query for doclistview and return results"""

import webnotes, json
import webnotes.defaults

@webnotes.whitelist()
def get():
	return compress(execute(**get_form_params()))

def get_form_params():
	data = webnotes._dict(webnotes.local.form_dict)

	del data["cmd"]

	if isinstance(data.get("filters"), basestring):
		data["filters"] = json.loads(data["filters"])
	if isinstance(data.get("fields"), basestring):
		data["fields"] = json.loads(data["fields"])
	if isinstance(data.get("docstatus"), basestring):
		data["docstatus"] = json.loads(data["docstatus"])
		
	return data
	
def execute(doctype, query=None, filters=None, fields=None, docstatus=None, 
		group_by=None, order_by=None, limit_start=0, limit_page_length=None, 
		as_list=False, with_childnames=False, debug=False):

	if query:
		return run_custom_query(query)
				
	if not filters: filters = []
	if not docstatus: docstatus = []

	args = prepare_args(doctype, filters, fields, docstatus, group_by, order_by, with_childnames)
	args.limit = add_limit(limit_start, limit_page_length)
	
	query = """select %(fields)s from %(tables)s where %(conditions)s
		%(group_by)s order by %(order_by)s %(limit)s""" % args
		
	return webnotes.conn.sql(query, as_dict=not as_list, debug=debug)
	
def prepare_args(doctype, filters, fields, docstatus, group_by, order_by, with_childnames):
	webnotes.local.reportview_tables = get_tables(doctype, fields)
	load_doctypes()
	remove_user_tags(doctype, fields)
	conditions = build_conditions(doctype, fields, filters, docstatus)
	
	args = webnotes._dict()
	
	if with_childnames:
		for t in webnotes.local.reportview_tables:
			if t != "`tab" + doctype + "`":
				fields.append(t + ".name as '%s:name'" % t[4:-1])
	
	# query dict
	args.tables = ', '.join(webnotes.local.reportview_tables)
	args.conditions = ' and '.join(conditions)
	args.fields = ', '.join(fields)
	
	args.order_by = order_by or webnotes.local.reportview_tables[0] + '.modified desc'
	args.group_by = group_by and (" group by " + group_by) or ""

	check_sort_by_table(args.order_by)
		
	return args

def compress(data):
	"""separate keys and values"""
	if not data: return data
	values = []
	keys = data[0].keys()
	for row in data:
		new_row = []
		for key in keys:
			new_row.append(row[key])
		values.append(new_row)
		
	return {
		"keys": keys,
		"values": values
	}
	
def check_sort_by_table(sort_by):
	"""check atleast 1 column selected from the sort by table """
	if "." in sort_by:
		tbl = sort_by.split('.')[0]
		if tbl not in webnotes.local.reportview_tables:
			if tbl.startswith('`'):
				tbl = tbl[4:-1]
			webnotes.msgprint("Please select atleast 1 column from '%s' to sort"\
				% tbl, raise_exception=1)

def run_custom_query(query):
	"""run custom query"""
	if '%(key)s' in query:
		query = query.replace('%(key)s', 'name')
	return webnotes.conn.sql(query, as_dict=1)

def load_doctypes():
	"""load all doctypes and roles"""
	import webnotes.model.doctype

	webnotes.local.reportview_roles = webnotes.get_roles()
	
	if not getattr(webnotes.local, "reportview_doctypes", None):
		webnotes.local.reportview_doctypes = {}

	for t in webnotes.local.reportview_tables:
		if t.startswith('`'):
			doctype = t[4:-1]
			if not webnotes.has_permission(doctype):
				raise webnotes.PermissionError, doctype
			webnotes.local.reportview_doctypes[doctype] = webnotes.model.doctype.get(doctype)
	
def remove_user_tags(doctype, fields):
	"""remove column _user_tags if not in table"""
	columns = get_table_columns(doctype)
	del_user_tags = False
	del_comments = False
	for fld in fields:
		if '_user_tags' in fld and not "_user_tags" in columns:
			del_user_tags = fld
		if '_comments' in fld and not "_comments" in columns:
			del_comments = fld

	if del_user_tags: del fields[fields.index(del_user_tags)]
	if del_comments: del fields[fields.index(del_comments)]

def add_limit(limit_start, limit_page_length):
	if limit_page_length:
		return 'limit %s, %s' % (limit_start, limit_page_length)
	else:
		return ''
		
def build_conditions(doctype, fields, filters, docstatus):
	"""build conditions"""	
	if docstatus:
		conditions = [webnotes.local.reportview_tables[0] + '.docstatus in (' + ','.join(docstatus) + ')']
	else:
		# default condition
		conditions = [webnotes.local.reportview_tables[0] + '.docstatus < 2']
	
	# make conditions from filters
	build_filter_conditions(filters, conditions)
	
	# join parent, child tables
	for tname in webnotes.local.reportview_tables[1:]:
		conditions.append(tname + '.parent = ' + webnotes.local.reportview_tables[0] + '.name')

	# match conditions
	match_conditions = build_match_conditions(doctype, fields)
	if match_conditions:
		conditions.append(match_conditions)
	
	return conditions
		
def build_filter_conditions(filters, conditions):
	"""build conditions from user filters"""
	from webnotes.utils import cstr
	if not getattr(webnotes.local, "reportview_tables", None):
		webnotes.local.reportview_tables = []
	
	for f in filters:
		if isinstance(f, basestring):
			conditions.append(f)
		else:
			tname = ('`tab' + f[0] + '`')
			if not tname in webnotes.local.reportview_tables:
				webnotes.local.reportview_tables.append(tname)
		
			# prepare in condition
			if f[2] in ['in', 'not in']:
				opts = ["'" + t.strip().replace("'", "\\'") + "'" for t in f[3].split(',')]
				f[3] = "(" + ', '.join(opts) + ")"
				conditions.append(tname + '.' + f[1] + " " + f[2] + " " + f[3])	
			else:
				if isinstance(f[3], basestring):
					f[3] = "'" + f[3].replace("'", "\\'") + "'"	
					conditions.append(tname + '.' + f[1] + " " + f[2] + " " + f[3])	
				else:
					conditions.append('ifnull(' + tname + '.' + f[1] + ",0) " + f[2] \
						+ " " + cstr(f[3]))
					
def build_match_conditions(doctype, fields=None, as_condition=True):
	"""add match conditions if applicable"""
	
	match_filters = {}
	match_conditions = []
	match = True

	if not getattr(webnotes.local, "reportview_tables", None) \
		or not getattr(webnotes.local, "reportview_doctypes", None):
		webnotes.local.reportview_tables = get_tables(doctype, fields)
		load_doctypes()

	if not getattr(webnotes.local, "reportview_roles", None):
		webnotes.local.reportview_roles = webnotes.get_roles()

	for d in webnotes.local.reportview_doctypes[doctype]:
		if d.doctype == 'DocPerm' and d.parent == doctype:
			if d.role in webnotes.local.reportview_roles:
				if d.match: # role applicable
					if ':' in d.match:
						document_key, default_key = d.match.split(":")
					else:
						default_key = document_key = d.match
					for v in webnotes.defaults.get_user_default_as_list(default_key, \
						webnotes.session.user) or ["** No Match **"]:
						if as_condition:
							match_conditions.append('`tab%s`.%s="%s"' % (doctype,
								document_key, v))
						else:
							if v:
								match_filters.setdefault(document_key, [])
								if v not in match_filters[document_key]:
									match_filters[document_key].append(v)
							
				elif d.read == 1 and d.permlevel == 0:
					# don't restrict if another read permission at level 0 
					# exists without a match restriction
					match = False
					match_filters = {}
	
	if as_condition:
		conditions = ""
		if match_conditions and match:
			conditions =  '('+ ' or '.join(match_conditions) +')'
		
		doctype_conditions = get_doctype_conditions(doctype)
		if doctype_conditions:
				conditions += ' and ' + doctype_conditions if conditions else doctype_conditions
		return conditions
	else:
		return match_filters
		
def get_doctype_conditions(doctype):
	from webnotes.model.code import load_doctype_module
	module = load_doctype_module(doctype)
	if module and hasattr(module, 'get_match_conditions'):
		return getattr(module, 'get_match_conditions')()

def get_tables(doctype, fields):
	"""extract tables from fields"""
	tables = ['`tab' + doctype + '`']

	# add tables from fields
	if fields:
		for f in fields:
			if "." not in f: continue
		
			table_name = f.split('.')[0]
			if table_name.lower().startswith('group_concat('):
				table_name = table_name[13:]
			if table_name.lower().startswith('ifnull('):
				table_name = table_name[7:]
			if not table_name[0]=='`':
				table_name = '`' + table_name + '`'
			if not table_name in tables:
				tables.append(table_name)	

	return tables

@webnotes.whitelist()
def save_report():
	"""save report"""
	from webnotes.model.doc import Document
	
	data = webnotes.local.form_dict
	if webnotes.conn.exists('Report', data['name']):
		d = Document('Report', data['name'])
	else:
		d = Document('Report')
		d.report_name = data['name']
		d.ref_doctype = data['doctype']
	
	d.report_type = "Report Builder"
	d.json = data['json']
	webnotes.bean([d]).save()
	webnotes.msgprint("%s saved." % d.name)
	return d.name

@webnotes.whitelist()
def export_query():
	"""export from report builder"""
	
	# TODO: validate use is allowed to export
	verify_export_allowed()
	
	ret = execute(**get_form_params())

	columns = [x[0] for x in webnotes.conn.get_description()]
	data = [['Sr'] + get_labels(columns),]

	# flatten dict
	cnt = 1
	for row in ret:
		flat = [cnt,]
		for c in columns:
			flat.append(row.get(c))
		data.append(flat)
		cnt += 1

	# convert to csv
	from cStringIO import StringIO
	import csv

	f = StringIO()
	writer = csv.writer(f)
	for r in data:
		# encode only unicode type strings and not int, floats etc.
		writer.writerow(map(lambda v: isinstance(v, unicode) and v.encode('utf-8') or v, r))

	f.seek(0)
	webnotes.response['result'] = unicode(f.read(), 'utf-8')
	webnotes.response['type'] = 'csv'
	webnotes.response['doctype'] = [t[4:-1] for t in webnotes.local.reportview_tables][0]

def verify_export_allowed():
	"""throw exception if user is not allowed to export"""
	webnotes.local.reportview_roles = webnotes.get_roles()
	if not ('Administrator' in webnotes.local.reportview_roles or \
		'System Manager' in webnotes.local.reportview_roles or \
		'Report Manager' in webnotes.local.reportview_roles):
		raise webnotes.PermissionError

def get_labels(columns):
	"""get column labels based on column names"""
	label_dict = {}
	for doctype in webnotes.local.reportview_doctypes:
		for d in webnotes.local.reportview_doctypes[doctype]:
			if d.doctype=='DocField' and d.fieldname:
				label_dict[d.fieldname] = d.label
	
	return map(lambda x: label_dict.get(x, x.title()), columns)

@webnotes.whitelist()
def delete_items():
	"""delete selected items"""
	import json
	from webnotes.model import delete_doc
	from webnotes.model.code import get_obj

	il = json.loads(webnotes.form_dict.get('items'))
	doctype = webnotes.form_dict.get('doctype')
	
	for d in il:
		try:
			dt_obj = get_obj(doctype, d)
			if hasattr(dt_obj, 'on_trash'):
				dt_obj.on_trash()
			delete_doc(doctype, d)
		except Exception, e:
			webnotes.errprint(webnotes.get_traceback())
			pass
		
@webnotes.whitelist()
def get_stats(stats, doctype):
	"""get tag info"""
	import json
	tags = json.loads(stats)
	stats = {}
	
	columns = get_table_columns(doctype)
	for tag in tags:
		if not tag in columns: continue
		tagcount = execute(doctype, fields=[tag, "count(*)"], 
			filters=["ifnull(%s,'')!=''" % tag], group_by=tag, as_list=True)
			
		if tag=='_user_tags':
			stats[tag] = scrub_user_tags(tagcount)
		else:
			stats[tag] = tagcount
			
	return stats

def scrub_user_tags(tagcount):
	"""rebuild tag list for tags"""
	rdict = {}
	tagdict = dict(tagcount)
	for t in tagdict:
		alltags = t.split(',')
		for tag in alltags:
			if tag:
				if not tag in rdict:
					rdict[tag] = 0
			
				rdict[tag] += tagdict[t]
	
	rlist = []
	for tag in rdict:
		rlist.append([tag, rdict[tag]])
	
	return rlist

def get_table_columns(table):
	res = webnotes.conn.sql("DESC `tab%s`" % table, as_dict=1)
	if res: return [r['Field'] for r in res]

# used in building query in queries.py
def get_match_cond(doctype, searchfield = 'name'):
	cond = build_match_conditions(doctype)

	if cond:
		cond = ' and ' + cond
	else:
		cond = ''
	return cond
