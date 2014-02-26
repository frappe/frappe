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

import frappe
import frappe.utils

def execute(site=None):
	"""
	execute jobs
	this method triggers the other scheduler events
	Database connection: Ideally it should be connected from outside, if there is
	no connection, it will connect from defs.py
	"""
	from datetime import datetime
	
	format = '%Y-%m-%d %H:%M:%S'
	
	if not frappe.db:
		frappe.connect(site=site)
	
	out = []

	nowtime = frappe.utils.now_datetime()
	last = frappe.db.get_global('scheduler_last_event')
	
	# set scheduler last event
	frappe.db.begin()
	frappe.db.set_global('scheduler_last_event', nowtime.strftime(format))
	frappe.db.commit()
	
	if last:
		last = datetime.strptime(last, format)

		if nowtime.day != last.day:
			# if first task of the day execute daily tasks
			out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - daily:' + trigger('daily'))

			if nowtime.month != last.month:
				out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - monthly:' + trigger('monthly'))
					
			if nowtime.weekday()==0:
				out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - weekly:' + trigger('weekly'))
			
		if nowtime.hour != last.hour:
			out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - hourly:' + trigger('hourly'))

	out.append(nowtime.strftime("%Y-%m-%d %H:%M:%S") + ' - all:' + trigger('all'))
	
	return '\n'.join(out)
	
def trigger(method):
	"""trigger method in startup.schedule_handler"""
	traceback = ""
	for scheduler_event in frappe.get_hooks().scheduler_event:
		event_name, handler = scheduler_event.split(":")
		
		if method==event_name:
			try:
				frappe.get_attr(handler)()
				frappe.db.commit()
			except Exception:
				traceback += log("Method: {method}, Handler: {handler}".format(method=method, handler=handler))
				traceback += log(frappe.get_traceback())
				frappe.db.rollback()
				
	return traceback or 'ok'

def log(method, message=None):
	"""log error in patch_log"""
	message = frappe.utils.cstr(message) + "\n" if message else ""
	message += frappe.get_traceback()
	
	if not (frappe.db and frappe.db._conn):
		frappe.connect()
	
	frappe.db.rollback()
	frappe.db.begin()

	d = frappe.doc("Scheduler Log")
	d.method = method
	d.error = message
	d.save()

	frappe.db.commit()
	
	return message
	
def get_errors(from_date, to_date, limit):
	errors = frappe.db.sql("""select modified, method, error from `tabScheduler Log`
		where date(modified) between %s and %s
		and error not like '%%[Errno 110] Connection timed out%%'
		order by modified limit %s""", (from_date, to_date, limit), as_dict=True)
	return ["""<p>Time: {modified}</p><pre><code>Method: {method}\n{error}</code></pre>""".format(**e)
		for e in errors]
		
def get_error_report(from_date=None, to_date=None, limit=10):
	from frappe.utils import get_url, now_datetime, add_days
	
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
