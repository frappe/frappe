# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
"""
Events:
	always
	daily
	monthly
	weekly
"""

from __future__ import unicode_literals, print_function

import frappe
import json
import schedule
import time
import MySQLdb
import frappe.utils
import os
from frappe.utils import get_sites
from datetime import datetime
from frappe.utils.background_jobs import enqueue, get_jobs, queue_timeout
from frappe.limits import has_expired
from frappe.utils.data import get_datetime, now_datetime
from frappe.core.doctype.user.user import STANDARD_USERS
from frappe.installer import update_site_config
from six import string_types

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def start_scheduler():
	'''Run enqueue_events_for_all_sites every 2 minutes (default).
	Specify scheduler_interval in seconds in common_site_config.json'''

	interval = frappe.get_conf().scheduler_interval or 240
	schedule.every(interval).seconds.do(enqueue_events_for_all_sites)

	while True:
		schedule.run_pending()
		time.sleep(1)

def enqueue_events_for_all_sites():
	'''Loop through sites and enqueue events that are not already queued'''

	if os.path.exists(os.path.join('.', '.restarting')):
		# Don't add task to queue if webserver is in restart mode
		return

	with frappe.init_site():
		jobs_per_site = get_jobs()
		sites = get_sites()

	for site in sites:
		try:
			enqueue_events_for_site(site=site, queued_jobs=jobs_per_site[site])
		except:
			# it should try to enqueue other sites
			print(frappe.get_traceback())

def enqueue_events_for_site(site, queued_jobs):
	try:
		frappe.init(site=site)
		if frappe.local.conf.maintenance_mode:
			return

		if frappe.local.conf.pause_scheduler:
			return

		frappe.connect()
		if is_scheduler_disabled():
			return

		enqueue_events(site=site, queued_jobs=queued_jobs)

		frappe.logger(__name__).debug('Queued events for site {0}'.format(site))

	except:
		frappe.logger(__name__).error('Exception in Enqueue Events for Site {0}'.format(site) +
			'\n' + frappe.get_traceback())
		raise

	finally:
		frappe.destroy()

def enqueue_events(site, queued_jobs):
	nowtime = frappe.utils.now_datetime()
	last = frappe.db.get_value('System Settings', 'System Settings', 'scheduler_last_event')

	# set scheduler last event
	frappe.db.set_value('System Settings', 'System Settings',
		'scheduler_last_event', nowtime.strftime(DATETIME_FORMAT),
		update_modified=False)
	frappe.db.commit()

	out = []
	if last:
		last = datetime.strptime(last, DATETIME_FORMAT)
		out = enqueue_applicable_events(site, nowtime, last, queued_jobs)

	return '\n'.join(out)

def enqueue_applicable_events(site, nowtime, last, queued_jobs=()):
	nowtime_str = nowtime.strftime(DATETIME_FORMAT)
	out = []

	enabled_events = get_enabled_scheduler_events()

	def trigger_if_enabled(site, event):
		if event in enabled_events:
			trigger(site, event, queued_jobs)
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
			trigger(site, "all", queued_jobs)

		if "hourly" not in enabled_events:
			trigger(site, "hourly", queued_jobs)

	if nowtime.hour != last.hour:
		trigger_if_enabled(site, "hourly")
		trigger_if_enabled(site, "hourly_long")

		if "all" not in enabled_events:
			trigger(site, "all", queued_jobs)

	trigger_if_enabled(site, "all")

	return out

def trigger(site, event, queued_jobs=(), now=False):
	"""trigger method in hooks.scheduler_events"""
	queue = 'long' if event.endswith('_long') else 'short'
	timeout = queue_timeout[queue]
	if not queued_jobs and not now:
		queued_jobs = get_jobs(site=site, queue=queue)

	if frappe.flags.in_test:
		frappe.flags.ran_schedulers.append(event)

	events = get_scheduler_events(event)
	if not events:
		return

	for handler in events:
		if not now:
			if handler not in queued_jobs:
				enqueue(handler, queue, timeout, event)
		else:
			scheduler_task(site=site, event=event, handler=handler, now=True)

def get_scheduler_events(event):
	'''Get scheduler events from hooks and integrations'''
	scheduler_events = frappe.cache().get_value('scheduler_events')
	if not scheduler_events:
		scheduler_events = frappe.get_hooks("scheduler_events")
		frappe.cache().set_value('scheduler_events', scheduler_events)

	return scheduler_events.get(event) or []

def log(method, message=None):
	"""log error in patch_log"""
	message = frappe.utils.cstr(message) + "\n" if message else ""
	message += frappe.get_traceback()

	if not (frappe.db and frappe.db._conn):
		frappe.connect()

	frappe.db.rollback()
	frappe.db.begin()

	d = frappe.new_doc("Error Log")
	d.method = method
	d.error = message
	d.insert(ignore_permissions=True)

	frappe.db.commit()

	return message

def get_enabled_scheduler_events():
	if 'enabled_events' in frappe.flags:
		return frappe.flags.enabled_events

	enabled_events = frappe.db.get_global("enabled_scheduler_events")
	if enabled_events:
		if isinstance(enabled_events, string_types):
			enabled_events = json.loads(enabled_events)

		return enabled_events

	return ["all", "hourly", "hourly_long", "daily", "daily_long",
		"weekly", "weekly_long", "monthly", "monthly_long"]

def is_scheduler_disabled():
	if frappe.conf.disable_scheduler:
		return True

	return not frappe.utils.cint(frappe.db.get_single_value("System Settings", "enable_scheduler"))

def toggle_scheduler(enable):
	frappe.db.set_value("System Settings", None, "enable_scheduler", 1 if enable else 0)

def enable_scheduler():
	toggle_scheduler(True)

def disable_scheduler():
	toggle_scheduler(False)

def get_errors(from_date, to_date, limit):
	errors = frappe.db.sql("""select modified, method, error from `tabError Log`
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
		return 1, """<h4>Error Logs (max {limit}):</h4>
			<p>URL: <a href="{url}" target="_blank">{url}</a></p><hr>{errors}""".format(
			limit=limit, url=get_url(), errors="<hr>".join(errors))
	else:
		return 0, "<p>No error logs</p>"

def scheduler_task(site, event, handler, now=False):
	'''This is a wrapper function that runs a hooks.scheduler_events method'''
	frappe.logger(__name__).info('running {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))
	try:
		if not now:
			frappe.connect(site=site)

		frappe.flags.in_scheduler = True
		frappe.get_attr(handler)()

	except Exception:
		frappe.db.rollback()
		traceback = log(handler, "Method: {event}, Handler: {handler}".format(event=event, handler=handler))
		frappe.logger(__name__).error(traceback)
		raise

	else:
		frappe.db.commit()

	frappe.logger(__name__).info('ran {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))


def reset_enabled_scheduler_events(login_manager):
	if login_manager.info.user_type == "System User":
		try:
			frappe.db.set_global('enabled_scheduler_events', None)
		except MySQLdb.OperationalError as e:
			if e.args[0]==1205:
				frappe.log_error(frappe.get_traceback(), "Error in reset_enabled_scheduler_events")
			else:
				raise
		else:
			is_dormant = frappe.conf.get('dormant')
			if is_dormant:
				update_site_config('dormant', 'None')

def disable_scheduler_on_expiry():
	if has_expired():
		disable_scheduler()

def restrict_scheduler_events_if_dormant():
	if is_dormant():
		restrict_scheduler_events()
		update_site_config('dormant', True)

def restrict_scheduler_events(*args, **kwargs):
	val = json.dumps(["hourly", "hourly_long", "daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long"])
	frappe.db.set_global('enabled_scheduler_events', val)

def is_dormant(since = 345600):
	last_active = get_datetime(get_last_active())
	# Get now without tz info
	now = now_datetime().replace(tzinfo=None)
	time_since_last_active = now - last_active
	if time_since_last_active.total_seconds() > since:  # 4 days
		return True
	return False

def get_last_active():
	return frappe.db.sql("""select max(ifnull(last_active, "2000-01-01 00:00:00")) from `tabUser`
		where user_type = 'System User' and name not in ({standard_users})"""\
		.format(standard_users=", ".join(["%s"]*len(STANDARD_USERS))),
		STANDARD_USERS)[0][0]
