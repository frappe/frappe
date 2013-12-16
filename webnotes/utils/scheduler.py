# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
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
import webnotes.utils

def execute(site=None):
	"""
	execute jobs
	this method triggers the other scheduler events
	Database connection: Ideally it should be connected from outside, if there is
	no connection, it will connect from defs.py
	"""
	from datetime import datetime
	
	format = '%Y-%m-%d %H:%M:%S'
	
	if not webnotes.conn:
		webnotes.connect(site=site)
	
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
			out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - daily:' + trigger('execute_daily'))

			if nowtime.month != last.month:
				out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - monthly:' + trigger('execute_monthly'))
					
			if nowtime.weekday()==0:
				out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - weekly:' + trigger('execute_weekly'))
			
		if nowtime.hour != last.hour:
			out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - hourly:' + trigger('execute_hourly'))

	out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - all:' + trigger('execute_all'))
	
	return '\n'.join(out)
	
def trigger(method):
	"""trigger method in startup.schedule_handler"""
	traceback = ""
	
	for scheduler_event in webnotes.get_hooks().scheduler_event:
		event_name, handler = scheduler_event.split(":")
		
		if method==event_name:
			try:
				webnotes.get_attr(handler)()
				webnotes.conn.commit()
			except Exception:
				traceback += log("Method: {method}, Handler: {handler}".format(method, handler))
				traceback += log(webnotes.get_traceback())
				webnotes.conn.rollback()
				
	return traceback or 'ok'

def log(method, message=None):
	"""log error in patch_log"""
	message = webnotes.utils.cstr(message) + "\n" if message else ""
	message += webnotes.get_traceback()
	
	if not (webnotes.conn and webnotes.conn._conn):
		webnotes.connect()
	
	webnotes.conn.rollback()
	webnotes.conn.begin()

	d = webnotes.doc("Scheduler Log")
	d.method = method
	d.error = message
	d.save()

	webnotes.conn.commit()
	
	return message

def report_errors():
	from webnotes.utils.email_lib import sendmail_to_system_managers
	from webnotes.utils import get_url
	
	errors = [("""<p>Time: %(modified)s</p>
<pre><code>%(error)s</code></pre>""" % d) for d in webnotes.conn.sql("""select modified, error 
		from `tabScheduler Log` where DATEDIFF(NOW(), modified) < 1 
		and error not like '%%[Errno 110] Connection timed out%%' 
		limit 10""", as_dict=True)]
		
	if errors:
		sendmail_to_system_managers("ERPNext Scheduler Failure Report", ("""
	<p>Dear System Managers,</p>
	<p>Reporting ERPNext failed scheduler events for the day (max 10):</p>
	<p>URL: <a href="%(url)s" target="_blank">%(url)s</a></p><hr>""" % {"url":get_url()}) + "<hr>".join(errors))

if __name__=='__main__':
	execute()
