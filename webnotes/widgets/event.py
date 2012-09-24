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

# Event
# -------------
from __future__ import unicode_literals
import webnotes

@webnotes.whitelist()
def get_cal_events(m_st, m_end):
	import webnotes.model.doc
	
	sql = webnotes.conn.sql

	# load owned events
	res1 = sql("select name from `tabEvent` WHERE ifnull(event_date,'2000-01-01') between '%s' and '%s' and owner = '%s' and event_type != 'Public' and event_type != 'Cancel'" % (m_st, m_end, webnotes.user.name))

	# load individual events
	res2 = sql("select t1.name from `tabEvent` t1, `tabEvent User` t2 where ifnull(t1.event_date,'2000-01-01') between '%s' and '%s' and t2.person = '%s' and t1.name = t2.parent and t1.event_type != 'Cancel'" % (m_st, m_end, webnotes.user.name))

	# load role events
	roles = webnotes.user.get_roles()
	myroles = ['t2.role = "%s"' % r for r in roles]
	myroles = '(' + (' OR '.join(myroles)) + ')'
	res3 = sql("select t1.name from `tabEvent` t1, `tabEvent Role` t2  where ifnull(t1.event_date,'2000-01-01') between '%s' and '%s' and t1.name = t2.parent and t1.event_type != 'Cancel' and %s" % (m_st, m_end, myroles))
	
	# load public events
	res4 = sql("select name from `tabEvent` where ifnull(event_date,'2000-01-01') between '%s' and '%s' and event_type='Public'" % (m_st, m_end))
	
	doclist, rl = [], []
	for r in res1 + res2 + res3 + res4:
		if not r in rl:
			doclist += webnotes.model.doc.get('Event', r[0])
			rl.append(r)
	
	return doclist


# Load Month Events
# -----------------

@webnotes.whitelist()
def load_month_events():
	from webnotes.utils import cint

	mm = webnotes.form_dict.get('month')
	yy = webnotes.form_dict.get('year')
	m_st = str(yy) + '-%.2i' % cint(mm) + '-01'
	m_end = str(yy) + '-%.2i' % cint(mm) + '-31'

	webnotes.response['docs'] = get_cal_events(m_st, m_end)