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
	try:
		import startup.schedule_handlers
		
		if hasattr(startup.schedule_handlers, method):
			getattr(startup.schedule_handlers, method)()
	except Exception:
		traceback += log(method)
	else:
		webnotes.conn.commit()
		
	try:
		cp = webnotes.bean("Control Panel", "Control Panel")
		cp.run_method(method)
	except Exception:
		traceback += log("Control Panel: "+method)
	else:
		webnotes.conn.commit()
		
	return traceback or 'ok'

def log(method, message=None):
	"""log error in patch_log"""
	message = webnotes.utils.cstr(message) + "\n" if message else ""
	message += webnotes.getTraceback()
	
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
	
def get_errors(from_date, to_date, limit):
	errors = webnotes.conn.sql("""select modified, method, error from `tabScheduler Log`
		where date(modified) between %s and %s
		and error not like '%%[Errno 110] Connection timed out%%'
		order by modified limit %s""", (from_date, to_date, limit), as_dict=True)
	return ["""<p>Time: {modified}</p><pre><code>Method: {method}\n{error}</code></pre>""".format(**e)
		for e in errors]
		
def get_error_report(from_date=None, to_date=None, limit=10):
	from webnotes.utils import get_url, now_datetime, add_days
	
	if not from_date:
		from_date = add_days(now_datetime().date(), -1)
	if not to_date:
		to_date = add_days(now_datetime().date(), -1)
	
	errors = get_errors(from_date, to_date, limit)
	
	if errors:
		return 1, """<h4>Scheduler Failed Events (max {limit}):</h4>
			<p>URL: <a href="{url}" target="_blank">{url}</a></p><hr>{errors}""".format(
			limit=limit, url=get_url(), errors="<hr>".join(errors))
	else:
		return 0, "<p>Scheduler didn't encounter any problems.</p>"

if __name__=='__main__':
	execute()
