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
from frappe.utils import get_sites
from datetime import datetime
from background_jobs import enqueue, get_jobs

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def enqueue_events(site, current_jobs):
	if is_scheduler_disabled():
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
		out = enqueue_applicable_events(site, nowtime, last, current_jobs)

	return '\n'.join(out)

def enqueue_applicable_events(site, nowtime, last, current_jobs):
	nowtime_str = nowtime.strftime(DATETIME_FORMAT)
	out = []

	enabled_events = get_enabled_scheduler_events()

	def trigger_if_enabled(site, event, now=False):
		if event in enabled_events:
			trigger(site, event, current_jobs, now=now)
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
			trigger(site, current_jobs, "all")

		if "hourly" not in enabled_events:
			trigger(site, current_jobs, "hourly")

	if nowtime.hour != last.hour:
		trigger_if_enabled(site, "hourly")
		trigger_if_enabled(site, "hourly_long")

	trigger_if_enabled(site, "all")

	return out

def trigger(site, event, current_jobs, now=False):
	"""trigger method in startup.schedule_handler"""
	if event.endswith("long"):
		queue = 'long'
		timeout = 1500
	else:
		queue = 'default'
		timeout = 300
	for handler in frappe.get_hooks("scheduler_events").get(event, []):
		if not now:
			if handler not in current_jobs:
				enqueue(handler, queue, timeout)
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


def scheduler_task(site, event, handler, now=False):
	traceback = ""
	frappe.get_logger(__name__).info('running {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))
	try:
		if not now:
			frappe.connect(site=site)
		frappe.get_attr(handler)()

	except Exception:
		frappe.db.rollback()
		traceback = log(handler, "Method: {event}, Handler: {handler}".format(event=event, handler=handler))
		frappe.get_logger(__name__).warn(traceback)
		raise

	else:
		frappe.db.commit()

	frappe.get_logger(__name__).info('ran {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))


def enqueue_scheduler_events():
	jobs_per_site = get_jobs()
	for site in get_sites():
		enqueue_events_for_site(site=site, current_jobs=jobs_per_site[site])

def enqueue_events_for_site(site, current_jobs):
	try:
		frappe.init(site=site)
		if frappe.local.conf.maintenance_mode or frappe.conf.disable_scheduler:
			return
		frappe.connect(site=site)
		enqueue_events(site, current_jobs)
	except:
		frappe.get_logger(__name__).error('Exception in Enqueue Events for Site {0}'.format(site))
		raise
	finally:
		frappe.destroy()