# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
"""
Events:
	always
	daily
	monthly
	weekly
"""
# imports - compatibility imports
from __future__ import print_function, unicode_literals

# imports - standard imports
import os
import time

# imports - third party imports
import schedule

# imports - module imports
import frappe
from frappe.core.doctype.user.user import STANDARD_USERS
from frappe.installer import update_site_config
from frappe.utils import get_datetime, get_sites, now_datetime
from frappe.utils.background_jobs import get_jobs

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def start_scheduler():
	"""Run enqueue_events_for_all_sites every 2 minutes (default).
	Specify scheduler_interval in seconds in common_site_config.json"""

	schedule.every(frappe.get_conf().scheduler_tick_interval or 60).seconds.do(
		enqueue_events_for_all_sites
	)

	while True:
		schedule.run_pending()
		time.sleep(1)


def enqueue_events_for_all_sites():
	"""Loop through sites and enqueue events that are not already queued"""

	if os.path.exists(os.path.join(".", ".restarting")):
		# Don't add task to queue if webserver is in restart mode
		return

	with frappe.init_site():
		sites = get_sites()

	for site in sites:
		try:
			enqueue_events_for_site(site=site)
		except Exception as e:
			print(e.__class__, "Failed to enqueue events for site: {}".format(site))


def enqueue_events_for_site(site):
	def log_and_raise():
		error_message = "Exception in Enqueue Events for Site {0}\n{1}".format(
			site, frappe.get_traceback()
		)
		frappe.logger("scheduler").error(error_message)

	try:
		frappe.init(site=site)
		frappe.connect()
		if is_scheduler_inactive():
			return

		enqueue_events(site=site)

		frappe.logger("scheduler").debug("Queued events for site {0}".format(site))
	except frappe.db.OperationalError as e:
		if frappe.db.is_access_denied(e):
			frappe.logger("scheduler").debug("Access denied for site {0}".format(site))
		else:
			log_and_raise()
	except Exception:
		log_and_raise()

	finally:
		frappe.destroy()


def enqueue_events(site):
	if schedule_jobs_based_on_activity():
		frappe.flags.enqueued_jobs = []
		queued_jobs = get_jobs(site=site, key="job_type").get(site) or []
		for job_type in frappe.get_all("Scheduled Job Type", ("name", "method"), dict(stopped=0)):
			if not job_type.method in queued_jobs:
				# don't add it to queue if still pending
				frappe.get_doc("Scheduled Job Type", job_type.name).enqueue()


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


def schedule_jobs_based_on_activity(check_time=None):
	"""Returns True for active sites defined by Activity Log
	Returns True for inactive sites once in 24 hours"""
	if is_dormant(check_time=check_time):
		# ensure last job is one day old
		last_job_timestamp = _get_last_modified_timestamp("Scheduled Job Log")
		if not last_job_timestamp:
			return True
		else:
			if ((check_time or now_datetime()) - last_job_timestamp).total_seconds() >= 86400:
				# one day is passed since jobs are run, so lets do this
				return True
			else:
				# schedulers run in the last 24 hours, do nothing
				return False
	else:
		# site active, lets run the jobs
		return True


def is_dormant(check_time=None):
	last_activity_log_timestamp = _get_last_modified_timestamp("Activity Log")
	since = (frappe.get_system_settings("dormant_days") or 4) * 86400
	if not last_activity_log_timestamp:
		return True
	if ((check_time or now_datetime()) - last_activity_log_timestamp).total_seconds() >= since:
		return True
	return False


def _get_last_modified_timestamp(doctype):
	timestamp = frappe.db.get_value(
		doctype, filters={}, fieldname="modified", order_by="modified desc"
	)
	if timestamp:
		return get_datetime(timestamp)


@frappe.whitelist()
def activate_scheduler():
	if is_scheduler_disabled():
		enable_scheduler()
	if frappe.conf.pause_scheduler:
		update_site_config("pause_scheduler", 0)
