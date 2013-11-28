# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

# Event
# -------------
from __future__ import unicode_literals
import webnotes

@webnotes.whitelist()
def get_cal_events(m_st, m_end):
	import webnotes.model.doc
	
	# load owned events
	res1 = webnotes.conn.sql("select name from `tabEvent` WHERE ifnull(event_date,'2000-01-01') between '%s' and '%s' and owner = '%s' and event_type != 'Public' and event_type != 'Cancel'" % (m_st, m_end, webnotes.user.name))

	# load individual events
	res2 = webnotes.conn.sql("select t1.name from `tabEvent` t1, `tabEvent User` t2 where ifnull(t1.event_date,'2000-01-01') between '%s' and '%s' and t2.person = '%s' and t1.name = t2.parent and t1.event_type != 'Cancel'" % (m_st, m_end, webnotes.user.name))

	# load role events
	roles = webnotes.user.get_roles()
	myroles = ['t2.role = "%s"' % r for r in roles]
	myroles = '(' + (' OR '.join(myroles)) + ')'
	res3 = webnotes.conn.sql("select t1.name from `tabEvent` t1, `tabEvent Role` t2  where ifnull(t1.event_date,'2000-01-01') between '%s' and '%s' and t1.name = t2.parent and t1.event_type != 'Cancel' and %s" % (m_st, m_end, myroles))
	
	# load public events
	res4 = webnotes.conn.sql("select name from `tabEvent` where ifnull(event_date,'2000-01-01') between '%s' and '%s' and event_type='Public'" % (m_st, m_end))
	
	doclist, rl = [], []
	for r in res1 + res2 + res3 + res4:
		if not r in rl:
			doclist += webnotes.model.doc.get('Event', r[0])
			rl.append(r)
	
	return doclist
