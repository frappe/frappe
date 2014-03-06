from __future__ import unicode_literals
from frappe.celery_app import app
import frappe
from frappe.cli import get_sites
from frappe.utils.file_lock import delete_lock

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@app.task()
def sync_queues():
	sites = get_sites()
	for site in sites:
		app.control.broadcast('add_consumer', arguments={'queue': site}, reply=True)

@app.task()
def scheduler_task(site, event, handler):
	from frappe.utils.scheduler import log
	traceback = ""
	try:
		frappe.init(site=site)
		frappe.connect()
		frappe.get_attr(handler)()
		frappe.db.commit()
		delete_lock(handler)
	except Exception:
		traceback += log("Method: {event}, Handler: {handler}".format(event=event, handler=handler))
		traceback += log(frappe.get_traceback())
		logger.warn(traceback)
		frappe.db.rollback()
		frappe.destroy()
		raise
	frappe.destroy()
	logger.info('ran {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))

@app.task()
def enqueue_scheduler_events():
	import frappe
	from frappe.utils.scheduler import execute
	logger.info('ran {handler} for {site} for event: {event}')
	for site in get_sites():
		execute(site)
