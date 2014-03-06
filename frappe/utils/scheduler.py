# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 
"""
Events:
	always
	daily
	monthly
	weekly
"""

from __future__ import unicode_literals

import frappe
import frappe.utils
from frappe.utils.file_lock import create_lock, check_lock, delete_lock, LockTimeoutError
from datetime import datetime

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def enqueue_events(site):
	# lock before queuing begins
	try:
		create_lock('scheduler')
	except LockTimeoutError:
		frappe.destroy()
		return
	
	if not frappe.db:
		# also does init
		frappe.connect(site=site)
		
	nowtime = frappe.utils.now_datetime()
	last = frappe.db.get_global('scheduler_last_event')
	
	# set scheduler last event
	frappe.db.begin()
	frappe.db.set_global('scheduler_last_event', nowtime.strftime(format))
	frappe.db.commit()
	
	if last:
		datetime.strptime(last, format)
		out = enqueue_applicable_events(site, nowtime, last)
	
	delete_lock('scheduler')
	
	return '\n'.join(out)
	
def enqueue_applicable_events(site, nowtime, last):
	nowtime_str = nowtime.strftime(DATETIME_FORMAT)
	out = []
	
	def _log(event):
		out.append("{time} - {event} - queued".format(time=nowtime_str, event=event))
	
	if nowtime.day != last.day:
		# if first task of the day execute daily tasks
		trigger(site, 'daily') and _log("daily")

		if nowtime.month != last.month:
			trigger(site, "monthly") and _log("monthly")
				
		if nowtime.weekday()==0:
			trigger(site, "weekly") and _log("weekly")
		
	if nowtime.hour != last.hour:
		trigger(site, "hourly") and _log("hourly")

	trigger(site, "all") and _log("all")
	
	return out
	
def trigger(site, event, now=False):
	"""trigger method in startup.schedule_handler"""
	from frappe.tasks import scheduler_task
	
	for scheduler_event in frappe.get_hooks().scheduler_event:
		event_name, handler = scheduler_event.split(":")
		if event==event_name and not check_lock(handler):
			if not now:
				result = scheduler_task.delay(site, event, handler)
				create_lock(handler)
			else:
				result = scheduler_task(site, event, handler)
	
	return result

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
