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
import webnotes.widgets.reportview
import webnotes.widgets.query_builder
from webnotes.utils import cstr
from startup.query_handlers import standard_queries

# this is called by the Link Field
@webnotes.whitelist()
def search_link(dt, txt, query=None, filters=None):
	search_widget(dt, txt, query, page_len=10, filters=filters)
	webnotes.response['results'] = build_for_autosuggest(webnotes.response["values"])

# this is called by the search box
@webnotes.whitelist()
def search_widget(doctype, txt, query=None, searchfield="name", start=0, 
	page_len=50, filters=None):
	if isinstance(filters, basestring):
		import json
		filters = json.loads(filters)
	if isinstance(filters, dict):
		filters = map(lambda f: [doctype, f[0], "=", f[1]], filters.items())
	if filters==None:
		filters = []

	meta = webnotes.get_doctype(doctype)
	
	if query and query.split()[0].lower()!="select":
		# by method
		webnotes.response["values"] = webnotes.get_method(query)(doctype, txt, 
			searchfield, start, page_len, filters)
	elif not query and doctype in standard_queries:
		# from standard queries
		search_widget(doctype, txt, standard_queries[doctype], 
			searchfield, start, page_len, filters)
	else:
		if query:
			# custom query
			webnotes.response["values"] = webnotes.conn.sql(scrub_custom_query(query, 
				searchfield, txt))
		else:
			# build from doctype
			if txt:
				filters.append([doctype, searchfield, "like", txt + "%"])
			if meta.get({"parent":doctype, "fieldname":"enabled", "fieldtype":"Check"}):
				filters.append([doctype, "enabled", "=", 1])
			if meta.get({"parent":doctype, "fieldname":"disabled", "fieldtype":"Check"}):
				filters.append([doctype, "disabled", "!=", 1])

			webnotes.response["values"] = webnotes.widgets.reportview.execute(doctype,
				filters=filters, fields = get_std_fields_list(meta, searchfield), 
				limit_start = start, limit_page_length=page_len, as_list=True)

def get_std_fields_list(meta, key):
	# get additional search fields
	sflist = meta[0].search_fields and meta[0].search_fields.split(",") or []
	sflist = ['name'] + sflist
	if not key in sflist:
		sflist = sflist + [key]

	return ['`tab%s`.`%s`' % (meta[0].name, f.strip()) for f in sflist]

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