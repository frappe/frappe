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

# Search
from __future__ import unicode_literals
import webnotes
import webnotes.widgets.query_builder
from webnotes.utils import cstr
from startup.query_handlers import standard_queries

# this is called when a new doctype is setup for search - to set the filters
@webnotes.whitelist()
def getsearchfields():
	sf = webnotes.conn.sql("""\
		SELECT value FROM `tabProperty Setter`
		WHERE doc_type=%s AND property='search_fields'""", \
		(webnotes.form_dict.get("doctype")))
	if not (sf and len(sf)>0 and sf[0][0]):
		sf = webnotes.conn.sql("select search_fields from tabDocType where name=%s", webnotes.form_dict.get("doctype"))
	sf = sf and sf[0][0] or ''
	sf = [s.strip() for s in sf.split(',')]
	if sf and sf[0]:
		res =  webnotes.conn.sql("select fieldname, label, fieldtype, options from tabDocField where parent='%s' and fieldname in (%s)" % (webnotes.form_dict.get("doctype","_NA"), '"'+'","'.join(sf)+'"'))
	else:
		res = []

	res = [[c or '' for c in r] for r in res]
	for r in res:
		if r[2]=='Select' and r[3] and r[3].startswith('link:'):
			dt = r[3][5:]
			ol = webnotes.conn.sql("select name from `tab%s` where docstatus!=2 order by name asc" % dt)
			r[3] = '\n'.join([''] + [o[0] for o in ol])

	webnotes.response['searchfields'] = [['name', 'ID', 'Data', '']] + res

# this is called by the Link Field
@webnotes.whitelist()
def search_link(dt, txt, query=None, args=None):
	search_widget(dt, txt, query, page_len=10, args=args)
	webnotes.response['results'] = build_for_autosuggest(webnotes.response["values"])

# this is called by the search box
@webnotes.whitelist()
def search_widget(doctype, txt, query=None, searchfield="name", start=0, page_len=50, args=None):
	if isinstance(args, basestring):
		import json
		args = json.loads(args)
		
	if query and query.split()[0].lower()!="select":
		webnotes.response["values"] = webnotes.get_method(query)(doctype, txt, 
			searchfield, start, page_len, args)
	elif not query and doctype in standard_queries:
		search_widget(doctype, txt, standard_queries[doctype], searchfield, start, page_len, args)
	else:
		if query:
			webnotes.response["values"] = webnotes.conn.sql(scrub_custom_query(query, 
				searchfield, txt))
		else:
			query = make_query(', '.join(get_std_fields_list(doctype, searchfield)), doctype, 
				searchfield, txt, start, page_len)

			webnotes.widgets.query_builder.runquery(query)

def make_query(fields, dt, key, txt, start, length):
	doctype = webnotes.get_doctype(dt)

	enabled_condition = ""
	if doctype.get({"parent":dt, "fieldname":"enabled", "fieldtype":"Check"}):
		enabled_condition = " AND ifnull(`tab%s`.`enabled`,0)=1" % dt
	if doctype.get({"parent":dt, "fieldname":"disabled", "fieldtype":"Check"}):
		enabled_condition = " AND ifnull(`tab%s`.`disabled`,0)!=1" % dt
	
	query = """select %(fields)s
		FROM `tab%(dt)s`
		WHERE `tab%(dt)s`.`%(key)s` LIKE '%(txt)s' 
		AND `tab%(dt)s`.docstatus != 2 %(enabled_condition)s
		ORDER BY `tab%(dt)s`.`%(key)s`
		ASC LIMIT %(start)s, %(len)s """ % {
			'fields': fields,
			'dt': dt,
			'key': key,
			'txt': txt + '%',
			'start': start,
			'len': length,
			'enabled_condition': enabled_condition
		}
	return query

def get_std_fields_list(dt, key):
	# get additional search fields
	sflist = webnotes.conn.sql("select search_fields from tabDocType where name = '%s'" % dt)
	sflist = sflist and sflist[0][0] and sflist[0][0].split(',') or []

	sflist = ['name'] + sflist
	if not key in sflist:
		sflist = sflist + [key]

	return ['`tab%s`.`%s`' % (dt, f.strip()) for f in sflist]

def build_for_autosuggest(res):
	results = []
	for r in res:
		info = ''
		if len(r) > 1:
			info = ', '.join([cstr(t) for t in r[1:]])
			if len(info) > 50:
				info = "<span title=\"%s\">%s...</span>" % (info, info[:50])

		results.append({'label':r[0], 'value':r[0], 'info':info})
	return results

def scrub_custom_query(query, key, txt):
	if '%(key)s' in query:
		query = query.replace('%(key)s', key)
	if '%s' in query:
		query = query.replace('%s', ((txt or '') + '%'))
	return query