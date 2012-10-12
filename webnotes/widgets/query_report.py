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

from __future__ import unicode_literals
import webnotes

@webnotes.whitelist()
def run():
	globals().update(webnotes.form_dict)
	
	if not query:
		webnotes.msgprint("Must specify a Query to run", raise_exception=1)
	
	if not doctype:
		webnotes.msgprint("Must specify DocType for permissions.", 
			raise_exception=1)
	
	if not ("tab" + doctype.lower()) in query.lower().split("from")[1].split("where")[0]:
		webnotes.msgprint("Specified DocType must appear in query.", 
			raise_exception=1)
	
	if not webnotes.has_permission(doctype, "read"):
		webnotes.msgprint("Must have read permission to access this report.", 
			raise_exception=1)
	
	if not query.lower().startswith("select"):
		webnotes.msgprint("Query must be a SELECT", raise_exception=True)
		
	result = [list(t) for t in webnotes.conn.sql(query)]
	columns = webnotes.conn.get_description()
	
	return {
		"result": result,
		"columns": [c[0] for c in columns]
	}