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

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

@webnotes.whitelist()
def get_events(start, end):
	roles = webnotes.get_roles()
	events = webnotes.conn.sql("""select name, subject, 
		starts_on, ends_on, owner, all_day, event_type
		from tabEvent where (
			(starts_on between %s and %s)
			or (ends_on between %s and %s)
		)
		and (event_type='Public' or owner=%s
		or exists(select * from `tabEvent User` where 
			`tabEvent User`.parent=tabEvent.name and person=%s)
		or exists(select * from `tabEvent Role` where 
			`tabEvent Role`.parent=tabEvent.name 
			and `tabEvent Role`.role in ('%s')))""" % ('%s', '%s', '%s', '%s', '%s', '%s', 
			"', '".join(roles)), (start, end, start, end,
			webnotes.session.user, webnotes.session.user), as_dict=1)
			
	return events