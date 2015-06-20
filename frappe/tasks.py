# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.scheduler import enqueue_events
from frappe.celery_app import get_celery, celery_task, task_logger, LONGJOBS_PREFIX
from frappe.utils import get_sites
from frappe.utils.file_lock import create_lock, delete_lock
from frappe.handler import execute_cmd
from frappe.async import set_task_status, END_LINE, get_std_streams
import frappe.utils.response
import sys

@celery_task()
def sync_queues():
	"""notifies workers to monitor newly added sites"""
	app = get_celery()
	shortjob_workers, longjob_workers = get_workers(app)

	if shortjob_workers:
		for worker in shortjob_workers:
			sync_worker(app, worker)

	if longjob_workers:
		for worker in longjob_workers:
			sync_worker(app, worker, prefix=LONGJOBS_PREFIX)

def get_workers(app):
	longjob_workers = []
	shortjob_workers = []

	active_queues = app.control.inspect().active_queues()
	for worker in active_queues:
		if worker.startswith(LONGJOBS_PREFIX):
			longjob_workers.append(worker)
		else:
			shortjob_workers.append(worker)

	return shortjob_workers, longjob_workers

def sync_worker(app, worker, prefix=''):
	active_queues = set(get_active_queues(app, worker))
	required_queues = set(get_required_queues(app, prefix=prefix))
	to_add = required_queues - active_queues
	to_remove = active_queues - required_queues
	for queue in to_add:
		app.control.broadcast('add_consumer', arguments={
				'queue': queue
		}, reply=True, destination=[worker])
	for queue in to_remove:
		app.control.broadcast('cancel_consumer', arguments={
				'queue': queue
		}, reply=True, destination=[worker])


def get_active_queues(app, worker):
	active_queues = app.control.inspect().active_queues()
	if not (active_queues and active_queues.get(worker)):
		return []
	return [queue['name'] for queue in active_queues[worker]]

def get_required_queues(app, prefix=''):
	ret = []
	for site in get_sites():
		ret.append('{}{}'.format(prefix, site))
	ret.append(app.conf['CELERY_DEFAULT_QUEUE'])
	return ret

@celery_task()
def scheduler_task(site, event, handler, now=False):
	from frappe.utils.scheduler import log
	traceback = ""
	task_logger.info('running {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))
	try:
		frappe.init(site=site)
		if not create_lock(handler):
			return
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

		if not now:
			frappe.destroy()

	task_logger.info('ran {handler} for {site} for event: {event}'.format(handler=handler, site=site, event=event))

@celery_task()
def enqueue_scheduler_events():
	for site in get_sites():
		enqueue_events_for_site.delay(site=site)

@celery_task()
def enqueue_events_for_site(site):
	try:
		frappe.init(site=site)
		if frappe.local.conf.maintenance_mode:
			return
		frappe.connect(site=site)
		enqueue_events(site)
	except:
		task_logger.error('Exception in Enqueue Events for Site {0}'.format(site))
		raise
	finally:
		frappe.destroy()

@celery_task()
def pull_from_email_account(site, email_account):
	try:
		frappe.init(site=site)
		frappe.connect(site=site)
		email_account = frappe.get_doc("Email Account", email_account)
		email_account.receive()
		frappe.db.commit()
	finally:
		frappe.destroy()


@celery_task(bind=True)
def run_async_task(self, site, user, cmd, form_dict):
	ret = {}
	frappe.init(site)
	frappe.connect()
	sys.stdout, sys.stderr = get_std_streams(self.request.id)
	frappe.local.stdout, frappe.local.stderr = sys.stdout, sys.stderr
	frappe.local.task_id = self.request.id
	frappe.cache()
	try:
		set_task_status(self.request.id, "Running")
		frappe.db.commit()
		frappe.set_user(user)
		# sleep(60)
		frappe.local.form_dict = frappe._dict(form_dict)
		execute_cmd(cmd, async=True)
		ret = frappe.local.response
	except Exception, e:
		frappe.db.rollback()
		set_task_status(self.request.id, "Failed")
		if not frappe.flags.in_test:
			frappe.db.commit()

		ret = frappe.local.response
		http_status_code = getattr(e, "http_status_code", 500)
		ret['status_code'] = http_status_code
		ret['exc'] = frappe.get_traceback()
		task_logger.error('Exception in running {}: {}'.format(cmd, ret['exc']))
	else:
		set_task_status(self.request.id, "Finished", response=ret)
		if not frappe.flags.in_test:
			frappe.db.commit()
	finally:
		sys.stdout.write('\n' + END_LINE)
		sys.stderr.write('\n' + END_LINE)
		if not frappe.flags.in_test:
			frappe.destroy()
		sys.stdout.close()
		sys.stderr.close()
		sys.stdout, sys.stderr = 1, 0
	return ret
