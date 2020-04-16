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
import frappe.utils
import os
from frappe.utils import get_sites
from datetime import datetime
from frappe.utils.background_jobs import enqueue, get_jobs, queue_timeout
from frappe.utils.data import get_datetime, now_datetime
from frappe.core.doctype.user.user import STANDARD_USERS
from frappe.installer import update_site_config
from six import string_types
from croniter import croniter

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

cron_map = {
	"yearly": "0 0 1 1 *",
	"annual": "0 0 1 1 *",
	"monthly": "0 0 1 * *",
	"monthly_long": "0 0 1 * *",
	"weekly": "0 0 * * 0",
	"weekly_long": "0 0 * * 0",
	"daily": "0 0 * * *",
	"daily_long": "0 0 * * *",
	"midnight": "0 0 * * *",
	"hourly": "0 * * * *",
	"hourly_long": "0 * * * *",
	"all": "0/" + str((frappe.get_conf().scheduler_interval or 240) // 60) + " * * * *",
}

def start_scheduler():
	'''Run enqueue_events_for_all_sites every 2 minutes (default).
	Specify scheduler_interval in seconds in common_site_config.json'''

	schedule.every(frappe.get_conf().scheduler_tick_interval or 60).seconds.do(enqueue_events_for_all_sites)

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
		except Exception as e:
			print(e.__class__, 'Failed to enqueue events for site: {}'.format(site))

def enqueue_events_for_site(site, queued_jobs):
	def log_and_raise():
		frappe.logger(__name__).error('Exception in Enqueue Events for Site {0}'.format(site) +
			'\n' + frappe.get_traceback())
		raise # pylint: disable=misplaced-bare-raise

	try:
		frappe.init(site=site)
		frappe.connect()
		if is_scheduler_inactive():
			return

		enqueue_events(site=site, queued_jobs=queued_jobs)

		frappe.logger(__name__).debug('Queued events for site {0}'.format(site))
	except frappe.db.OperationalError as e:
		if frappe.db.is_access_denied(e):
			frappe.logger(__name__).debug('Access denied for site {0}'.format(site))
		else:
			log_and_raise()
	except:
		log_and_raise()

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

	def trigger_if_enabled(site, event, last, queued_jobs):
		trigger(site, event, last, queued_jobs)
		_log(event)

	def _log(event):
		out.append("{time} - {event} - queued".format(time=nowtime_str, event=event))

	for event in enabled_events:
		trigger_if_enabled(site, event, last, queued_jobs)

	if "all" not in enabled_events:
		trigger_if_enabled(site, "all", last, queued_jobs)

	return out

def trigger(site, event, last=None, queued_jobs=(), now=False):
	"""Trigger method in hooks.scheduler_events."""

	queue = 'long' if event.endswith('_long') else 'short'
	timeout = queue_timeout[queue]
	if not queued_jobs and not now:
		queued_jobs = get_jobs(site=site, queue=queue)

	if frappe.flags.in_test:
		frappe.flags.ran_schedulers.append(event)

	events_from_hooks = get_scheduler_events(event)
	if not events_from_hooks:
		return

	events = events_from_hooks
	if not now:
		events = []
		if event == "cron":
			for e in events_from_hooks:
				e = cron_map.get(e, e)
				if croniter.is_valid(e):
					if croniter(e, last).get_next(datetime) <= frappe.utils.now_datetime():
						events.extend(events_from_hooks[e])
				else:
					frappe.log_error("Cron string " + e + " is not valid", "Error triggering cron job")
					frappe.logger(__name__).error('Exception in Trigger Events for Site {0}, Cron String {1}'.format(site, e))

		else:
			if croniter(cron_map[event], last).get_next(datetime) <= frappe.utils.now_datetime():
				events.extend(events_from_hooks)

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
	if 'enabled_events' in frappe.flags and frappe.flags.enabled_events:
		return frappe.flags.enabled_events

	enabled_events = frappe.db.get_global("enabled_scheduler_events")
	if frappe.flags.in_test:
		# TEMP for debug: this test fails randomly
		print('found enabled_scheduler_events {0}'.format(enabled_events))

	if enabled_events:
		if isinstance(enabled_events, string_types):
			enabled_events = json.loads(enabled_events)
		return enabled_events

	return ["all", "hourly", "hourly_long", "daily", "daily_long",
		"weekly", "weekly_long", "monthly", "monthly_long", "cron"]

def is_scheduler_inactive():
	if frappe.local.conf.maintenance_mode:
		return True

	if frappe.local.conf.pause_scheduler:
		return True

	if is_scheduler_disabled():
		return True

	return False

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
			if frappe.db.get_global('enabled_scheduler_events'):
				# clear restricted events, someone logged in!
				frappe.db.set_global('enabled_scheduler_events', None)
		except frappe.db.InternalError as e:
			if frappe.db.is_timedout(e):
				frappe.log_error(frappe.get_traceback(), "Error in reset_enabled_scheduler_events")
			else:
				raise
		else:
			is_dormant = frappe.conf.get('dormant')
			if is_dormant:
				update_site_config('dormant', 'None')


def restrict_scheduler_events_if_dormant():
	if is_dormant():
		restrict_scheduler_events()
		update_site_config('dormant', True)

def restrict_scheduler_events(*args, **kwargs):
	val = json.dumps(["hourly", "hourly_long", "daily", "daily_long", "weekly", "weekly_long", "monthly", "monthly_long", "cron"])
	frappe.db.set_global('enabled_scheduler_events', val)

def is_dormant(since = 345600):
	last_user_activity = get_last_active()
	if not last_user_activity:
		# no user has ever logged in, so not yet used
		return False
	last_active = get_datetime(last_user_activity)
	# Get now without tz info
	now = now_datetime().replace(tzinfo=None)
	time_since_last_active = now - last_active
	if time_since_last_active.total_seconds() > since:  # 4 days
		return True
	return False

def get_last_active():
	return frappe.db.sql("""SELECT MAX(`last_active`) FROM `tabUser`
		WHERE `user_type` = 'System User' AND `name` NOT IN ({standard_users})"""
		.format(standard_users=", ".join(["%s"]*len(STANDARD_USERS))),
		STANDARD_USERS)[0][0]

@frappe.whitelist()
def activate_scheduler():
	if is_scheduler_disabled():
		enable_scheduler()
	if frappe.conf.pause_scheduler:
		update_site_config('pause_scheduler', 0)
