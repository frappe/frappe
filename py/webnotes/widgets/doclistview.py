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

"""build query for doclistview and return results"""

import webnotes, json

@webnotes.whitelist()
def get(arg=None):
	"""
	build query
	
	gets doctype, subject, filters
	limit_start, limit_page_length
	"""
	
	data = webnotes.form_dict
	filters = json.loads(data['filters'])
	fields = json.loads(data['fields'])
		
	tables = ['`tab' + data['doctype'] + '`']

	# keep _user_tags only if it exists in table
	columns = get_table_columns(data['doctype'])
	if '_user_tags' not in columns: del fields[fields.index('_user_tags')]

	docstatus = json.loads(data['docstatus'])
	if docstatus:
		conditions = [tables[0] + '.docstatus in (' + ','.join(docstatus) + ')']
	else:
		conditions = [tables[0] + '.docstatus < 2']
	# add table explict to field
	joined = [tables[0]]
	
	# make conditions from filters
	for f in filters:
		tname = ('`tab' + f[0] + '`')
		if not tname in tables:
			tables.append(tname)
		
		# prepare in condition
		if f[2]=='in':
			opts = ["'" + t.strip().replace("'", "\'") + "'" for t in f[3].split(',')]
			f[3] = "(" + ', '.join(opts) + ")"
		else:
			f[3] = "'" + f[3].replace("'", "\'") + "'"	
		
		conditions.append(tname + '.' + f[1] + " " + f[2] + " " + f[3])	
		
		if not tname in joined:
			conditions.append(tname + '.parent = ' + tables[0] + '.name')
			joined.append(tname)
			
	data['tables'] = ', '.join(tables)
	data['conditions'] = ' and '.join(conditions)
	data['fields'] = ', '.join(fields)
	if not data.get('order_by'):
		data['order_by'] = tables[0] + '.modified desc'
	
	query = """select %(fields)s from %(tables)s where %(conditions)s
		order by %(order_by)s
		limit %(limit_start)s, %(limit_page_length)s""" % data
	return webnotes.conn.sql(query, as_dict=1)
	
@webnotes.whitelist()
def delete_items():
	"""delete selected items"""
	import json
	from webnotes.model import delete_doc
	from webnotes.model.code import get_obj

	il = json.loads(webnotes.form_dict.get('items'))
	doctype = webnotes.form_dict.get('doctype')
	
	for d in il:
		dt_obj = get_obj(doctype, d)
		if hasattr(dt_obj, 'on_trash'):
			dt_obj.on_trash()
		delete_doc(doctype, d)
		
@webnotes.whitelist()
def get_stats():
	"""get tag info"""
	import json
	tags = json.loads(webnotes.form_dict.get('stats'))
	doctype = webnotes.form_dict['doctype']
	stats = {}
	
	columns = get_table_columns(doctype)
	for tag in tags:
		if not tag in columns: continue
		tagcount = webnotes.conn.sql("""select %(tag)s, count(*) 
			from `tab%(doctype)s` 
			where ifnull(%(tag)s, '')!=''
			group by %(tag)s;""" % locals(), as_list=1)
			
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
