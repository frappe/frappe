# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.scheduler import enqueue_events
from frappe.celery_app import get_celery, celery_task, task_logger, get_queue, LONGJOBS_PREFIX
from frappe.cli import get_sites
from frappe.utils.file_lock import delete_lock

@celery_task()
def sync_queues():
	"""notifies workers to monitor newly added sites"""
	app = get_celery()
	shortjob_workers, longjob_workers = get_workers(app)

	for site in get_sites():
		if shortjob_workers:
			app.control.broadcast('add_consumer', arguments=get_queue(site), 
				reply=True, destination=shortjob_workers)
		
		if longjob_workers:
			app.control.broadcast('add_consumer', arguments=get_queue(site, LONGJOBS_PREFIX),
				reply=True, destination=longjob_workers)
			
def get_workers(app):
	longjob_workers = []
	shortjob_workers = []

	active_queues = app.control.inspect().active_queues()
	for worker in active_queues.keys():
		if worker.startswith(LONGJOBS_PREFIX):
			longjob_workers.append(worker)
		else:
			shortjob_workers.append(worker)
	
	return shortjob_workers, longjob_workers

@celery_task()
def scheduler_task(site, event, handler, now=False):
	from frappe.utils.scheduler import log
	traceback = ""
	task_logger.info('running {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))
	try:
		if not now:
			frappe.connect(site=site)
		frappe.get_attr(handler)()
	
	except Exception:
		frappe.db.rollback()
		traceback = log(handler, "Method: {event}, Handler: {handler}".format(event=event, handler=handler))
		task_logger.warn(traceback)
		raise
		
	else:
		frappe.db.commit()

	finally:
		delete_lock(handler)
		frappe.destroy()

	task_logger.info('ran {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))

@celery_task()
def enqueue_scheduler_events():
	for site in get_sites():
		enqueue_events(site)
