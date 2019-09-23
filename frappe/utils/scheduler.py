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

import frappe, os, time
import schedule
from frappe.utils import now_datetime, get_datetime
from frappe.utils import get_sites
from frappe.core.doctype.user.user import STANDARD_USERS
from frappe.utils.background_jobs import get_jobs

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def start_scheduler():
	'''Run enqueue_events_for_all_sites every 2 minutes (default).
	Specify scheduler_interval in seconds in common_site_config.json'''

	schedule.every(60).seconds.do(enqueue_events_for_all_sites)

	while True:
		schedule.run_pending()
		time.sleep(1)

def enqueue_events_for_all_sites():
	'''Loop through sites and enqueue events that are not already queued'''

	if os.path.exists(os.path.join('.', '.restarting')):
		# Don't add task to queue if webserver is in restart mode
		return

	with frappe.init_site():
		sites = get_sites()

	for site in sites:
		try:
			enqueue_events_for_site(site=site)
		except:
			# it should try to enqueue other sites
			print(frappe.get_traceback())

def enqueue_events_for_site(site):
	def log_and_raise():
		frappe.logger(__name__).error('Exception in Enqueue Events for Site {0}'.format(site) +
			'\n' + frappe.get_traceback())
		raise # pylint: disable=misplaced-bare-raise

	try:
		frappe.init(site=site)
		frappe.connect()
		if is_scheduler_inactive():
			return

		enqueue_events(site=site)

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

def enqueue_events(site):
	frappe.flags.enqueued_jobs = []
	queued_jobs = get_jobs(key='job_type').get(site) or []
	for job_type in frappe.get_all('Scheduled Job Type', dict(stopped=0)):
		if not job_type.method in queued_jobs:
			# don't add it to queue if still pending
			frappe.get_doc('Scheduled Job Type', job_type.name).enqueue()

def is_scheduler_inactive():
	if frappe.local.conf.maintenance_mode:
		return True

	if frappe.local.conf.pause_scheduler:
		return True

	if is_scheduler_disabled():
		return True

	if is_dormant():
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

def is_dormant(since = 345600):
	last_user_activity = get_last_active()
	if not last_user_activity:
		# no user has ever logged in, so not yet used
		return False

	if now_datetime() - get_datetime(last_user_activity) > since:  # 4 days
		return True

	return False

def get_last_active():
	return frappe.db.sql("""SELECT MAX(`last_active`) FROM `tabUser`
		WHERE `user_type` = 'System User' AND `name` NOT IN ({standard_users})"""
		.format(standard_users=", ".join(["%s"]*len(STANDARD_USERS))),
		STANDARD_USERS)[0][0]
