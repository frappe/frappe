# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals, absolute_import

from celery import Celery

# initiate logger
from celery.utils.log import get_task_logger
task_logger = get_task_logger(__name__)

from datetime import timedelta
import frappe
import os
import threading
import time

SITES_PATH = os.environ.get('SITES_PATH', '.')

# defaults
DEFAULT_CELERY_BROKER = "redis://localhost"
DEFAULT_CELERY_BACKEND = "redis://localhost"
DEFAULT_SCHEDULER_INTERVAL = 300
LONGJOBS_PREFIX = "longjobs@"
ASYNC_TASKS_PREFIX = "async@"

_app = None
def get_celery():
	global _app
	if not _app:
		_app = get_celery_app()
	return _app

def get_celery_app():
	conf = frappe.get_site_config(sites_path=SITES_PATH)
	app = Celery('frappe',
			broker=conf.celery_broker or DEFAULT_CELERY_BROKER,
			backend=conf.async_redis_server or DEFAULT_CELERY_BACKEND)

	app.autodiscover_tasks(frappe.get_all_apps(with_frappe=True, with_internal_apps=False,
		sites_path=SITES_PATH))
	app.conf.CELERY_SEND_EVENTS = True
	app.conf.CELERY_TASK_SERIALIZER = 'json'
	app.conf.CELERY_ACCEPT_CONTENT = ['json']
	app.conf.CELERY_TIMEZONE = 'UTC'
	app.conf.CELERY_RESULT_SERIALIZER = 'json'
	app.conf.CELERY_TASK_RESULT_EXPIRES = timedelta(0, 3600)

	if conf.celery_queue_per_site:
		app.conf.CELERY_ROUTES = (SiteRouter(), AsyncTaskRouter())

	app.conf.CELERYBEAT_SCHEDULE = get_beat_schedule(conf)

	if conf.celery_error_emails:
		app.conf.CELERY_SEND_TASK_ERROR_EMAILS = True
		for k, v in conf.celery_error_emails.iteritems():
			setattr(app.conf, k, v)

	return app

class SiteRouter(object):
	def route_for_task(self, task, args=None, kwargs=None):
		if hasattr(frappe.local, 'site'):
			if kwargs and kwargs.get("event", "").endswith("_long"):
				return get_queue(frappe.local.site, LONGJOBS_PREFIX)
			else:
				return get_queue(frappe.local.site)

		return None

class AsyncTaskRouter(object):
	def route_for_task(self, task, args=None, kwargs=None):
		if task == "frappe.tasks.run_async_task" and hasattr(frappe.local, 'site'):
			return get_queue(frappe.local.site, ASYNC_TASKS_PREFIX)

def get_queue(site, prefix=None):
	return {'queue': "{}{}".format(prefix or "", site)}

def get_beat_schedule(conf):
	schedule = {
		'scheduler': {
			'task': 'frappe.tasks.enqueue_scheduler_events',
			'schedule': timedelta(seconds=conf.scheduler_interval or DEFAULT_SCHEDULER_INTERVAL)
		},
	}

	if conf.celery_queue_per_site:
		schedule['sync_queues'] = {
			'task': 'frappe.tasks.sync_queues',
			'schedule': timedelta(seconds=conf.scheduler_interval or DEFAULT_SCHEDULER_INTERVAL)
		}

	return schedule

def celery_task(*args, **kwargs):
	func = get_celery().task(*args, **kwargs)
	return func

def make_async_task(args):
	task = frappe.new_doc("Async Task")
	task.update(args)
	task.status = "Queued"
	task.set_docstatus_user_and_timestamp()
	task.db_insert()

def run_test():
	result = test.delay(site=frappe.local.site)
	result = result.get(propagate=False)
	print result

@celery_task()
def test(site=None):
	time.sleep(2)
	raise Exception
	print "task"

class MonitorThread(object):
	def __init__(self, celery_app, interval=1):
		self.celery_app = celery_app
		self.interval = interval

		self.state = self.celery_app.events.State()

		self.thread = threading.Thread(target=self.run, args=())
		self.thread.daemon = True
		self.thread.start()

	def catchall(self, event):
		if event['type'] != 'worker-heartbeat':
			self.state.event(event)

			if not 'uuid' in event:
				return

			task = self.state.tasks.get(event['uuid'])
			info = task.info()

			if 'enqueue_events_for_site' in event['name']:
				# don't log enqueue events
				return

			try:
				kwargs = eval(info.get('kwargs'))

				if 'site' in kwargs:
					frappe.connect(kwargs['site'])

					if event['type']=='task-received':
						make_async_task({'name': event['uuid'], 'task_name': event['name']})

					if event['type']=='task-succeeded':
						task = frappe.get_doc("Async Task", event['uuid'])
						task.status = 'Succeeded'
						task.result = info.get('result')
						task.runtime = info.get('runtime')
						task.set_docstatus_user_and_timestamp()
						task.db_update()

					if event['type']=='task-failed':
						task = frappe.get_doc("Async Task", event['uuid'])
						task.status = 'Failed'
						task.traceback = event.get('traceback') or event.get('exception')
						task.traceback = frappe.as_json(info) + "\n\n" + task.traceback
						task.runtime = info.get('runtime')
						task.set_docstatus_user_and_timestamp()
						task.db_update()

					frappe.db.commit()
			except Exception:
				print frappe.get_traceback()
			finally:
				frappe.destroy()


	def run(self):

		while True:
			try:
				with self.celery_app.connection() as connection:
					recv = self.celery_app.events.Receiver(connection, handlers={
						'*': self.catchall
					})
					recv.capture(limit=None, timeout=None, wakeup=True)

			except (KeyboardInterrupt, SystemExit):
				raise

			except Exception:
				# unable to capture
				pass

			time.sleep(self.interval)


if __name__ == '__main__':
	app = get_celery()
	MonitorThread(app)
	app.start()
