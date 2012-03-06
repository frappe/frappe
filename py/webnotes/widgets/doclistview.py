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
	conditions = [tables[0] + '.docstatus < 2']
	joined = [tables[0]]
	
	# make conditions from filters
	for f in filters:
		tname = ('`tab' + f[0] + '`')
		if not tname in tables:
			tables.append(tname)
		
		conditions.append(tname + '.' + f[1] + " " + f[2] + " '" + f[3].replace("'", "\'") + "'")	
		
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
	return webnotes.conn.sql(query, as_dict=1, debug=1)