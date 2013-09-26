# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
Scheduler will call the following events from the module
`startup.schedule_handler` and Control Panel (for server scripts)

execute_always
execute_daily
execute_monthly
execute_weekly

The scheduler should be called from a cron job every x minutes (5?) depending
on the need.
"""

import webnotes
def execute():
	"""
	execute jobs
	this method triggers the other scheduler events
	Database connection: Ideally it should be connected from outside, if there is
	no connection, it will connect from defs.py
	"""
	from datetime import datetime
	import webnotes.utils
	
	format = '%Y-%m-%d %H:%M:%S'
	
	if not webnotes.conn:
		webnotes.connect()
	
	out = []

	nowtime = webnotes.utils.now_datetime()
	last = webnotes.conn.get_global('scheduler_last_event')
	
	# set scheduler last event
	webnotes.conn.begin()
	webnotes.conn.set_global('scheduler_last_event', nowtime.strftime(format))
	webnotes.conn.commit()
	
	if last:
		last = datetime.strptime(last, format)

		if nowtime.day != last.day:
			# if first task of the day execute daily tasks
			out.append('daily:' + trigger('execute_daily'))

			if nowtime.month != last.month:
				out.append('monthly:' + trigger('execute_monthly'))
					
			if nowtime.weekday()==0:
				out.append('weekly:' + trigger('execute_weekly'))
			
		if nowtime.hour != last.hour:
			out.append('hourly:' + trigger('execute_hourly'))

	out.append('all:' + trigger('execute_all'))
	
	return '\n'.join(out)
	
def trigger(method):
	"""trigger method in startup.schedule_handler"""
	try:
		import startup.schedule_handlers
		
		if hasattr(startup.schedule_handlers, method):
			webnotes.conn.begin()
			getattr(startup.schedule_handlers, method)()
			webnotes.conn.commit()
			return 'ok'
		
	except Exception:
		return log(method)
		
	try:
		cp = webnotes.bean("Control Panel", "Control Panel")
		cp.run_method(method)
	except Exception:
		return log(method)

def log(method):
	"""log error in patch_log"""
	import webnotes
	
	if not (webnotes.conn and webnotes.conn._conn):
		webnotes.connect()
	
	webnotes.conn.rollback()
	traceback = webnotes.getTraceback()

	import webnotes.utils
	webnotes.conn.begin()
	d = webnotes.doc("Scheduler Log")
	d.method = method
	d.error = traceback
	d.save()
	webnotes.conn.commit()
	
	return traceback

def report_errors():
	from webnotes.utils.email_lib import sendmail_to_system_managers
	from webnotes.utils import get_url
	
	errors = [("""<p>Time: %(modified)s</p>
<pre><code>%(error)s</code></pre>""" % d) for d in webnotes.conn.sql("""select modified, error 
		from `tabScheduler Log` where DATEDIFF(NOW(), modified) < 1 
		and error not like '%%[Errno 111] Connection refused%%' 
		limit 10""", as_dict=True)]
		
	if errors:
		sendmail_to_system_managers("ERPNext Scheduler Failure Report", ("""
	<p>Dear System Managers,</p>
	<p>Reporting ERPNext failed scheduler events for the day (max 10):</p>
	<p>URL: <a href="%(url)s" target="_blank">%(url)s</a></p><hr>""" % {"url":get_url()}) + "<hr>".join(errors))

if __name__=='__main__':
	execute()
