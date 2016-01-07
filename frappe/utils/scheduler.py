# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
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
import json
import frappe.utils
from frappe.utils.file_lock import create_lock, check_lock, delete_lock
from datetime import datetime

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def enqueue_events(site):
	if is_scheduler_disabled():
		return

	# lock before queuing begins
	lock = create_lock('scheduler')
	if not lock:
		return

	nowtime = frappe.utils.now_datetime()
	last = frappe.db.get_value('System Settings', 'System Settings', 'scheduler_last_event')

	# set scheduler last event
	frappe.db.begin()
	frappe.db.set_value('System Settings', 'System Settings', 'scheduler_last_event', nowtime.strftime(DATETIME_FORMAT), update_modified=False)
	frappe.db.commit()

	out = []
	if last:
		last = datetime.strptime(last, DATETIME_FORMAT)
		out = enqueue_applicable_events(site, nowtime, last)

	delete_lock('scheduler')

	return '\n'.join(out)

def enqueue_applicable_events(site, nowtime, last):
	nowtime_str = nowtime.strftime(DATETIME_FORMAT)
	out = []

	enabled_events = get_enabled_scheduler_events()

	def trigger_if_enabled(site, event, now=False):
		if event in enabled_events:
			trigger(site, event, now=now)
			_log(event)

	def _log(event):
		out.append("{time} - {event} - queued".format(time=nowtime_str, event=event))

	if nowtime.day != last.day:
		# if first task of the day execute daily tasks
		trigger_if_enabled(site, "daily")
		trigger_if_enabled(site, "daily_long")

		if nowtime.month != last.month:
			trigger_if_enabled(site, "monthly")
			trigger_if_enabled(site, "monthly_long")

		if nowtime.weekday()==0:
			trigger_if_enabled(site, "weekly")
			trigger_if_enabled(site, "weekly_long")

		if "all" not in enabled_events:
			trigger(site, "all")

		if "hourly" not in enabled_events:
			trigger(site, "hourly")

	if nowtime.hour != last.hour:
		trigger_if_enabled(site, "hourly")
		trigger_if_enabled(site, "hourly_long")

	trigger_if_enabled(site, "all")

	return out

def trigger(site, event, now=False):
	"""trigger method in startup.schedule_handler"""
	from frappe.tasks import scheduler_task

	for handler in frappe.get_hooks("scheduler_events").get(event, []):
		if not check_lock(handler):
			if not now:
				scheduler_task.delay(site=site, event=event, handler=handler)
			else:
				scheduler_task(site=site, event=event, handler=handler, now=True)

	if frappe.flags.in_test:
		frappe.flags.ran_schedulers.append(event)

def log(method, message=None):
	"""log error in patch_log"""
	message = frappe.utils.cstr(message) + "\n" if message else ""
	message += frappe.get_traceback()

	if not (frappe.db and frappe.db._conn):
		frappe.connect()

	frappe.db.rollback()
	frappe.db.begin()

	d = frappe.new_doc("Scheduler Log")
	d.method = method
	d.error = message
	d.insert(ignore_permissions=True)

	frappe.db.commit()

	return message

def get_enabled_scheduler_events():
	enabled_events = frappe.db.get_global("enabled_scheduler_events")
	if enabled_events:
		return json.loads(enabled_events)
	return ["all", "hourly", "hourly_long", "daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long"]

def is_scheduler_disabled():
	if frappe.conf.disable_scheduler:
		return True
	return not frappe.utils.cint(frappe.db.get_single_value("System Settings", "enable_scheduler"))

def toggle_scheduler(enable):
	ss = frappe.get_doc("System Settings")
	ss.enable_scheduler = 1 if enable else 0
	ss.flags.ignore_mandatory = True
	ss.save()

def enable_scheduler():
	toggle_scheduler(True)

def disable_scheduler():
	toggle_scheduler(False)

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

