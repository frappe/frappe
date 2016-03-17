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
	conf = get_site_config()
	app = Celery('frappe',
			broker=conf.redis_queue or conf.celery_broker or DEFAULT_CELERY_BROKER,
			backend=conf.redis_queue or conf.async_redis_server or DEFAULT_CELERY_BACKEND)

	app.autodiscover_tasks(frappe.get_all_apps(with_internal_apps=False,
		sites_path=SITES_PATH))

	app.conf.CELERY_TASK_SERIALIZER = 'json'
	app.conf.CELERY_ACCEPT_CONTENT = ['json']
	app.conf.CELERY_TIMEZONE = 'UTC'
	app.conf.CELERY_RESULT_SERIALIZER = 'json'
	app.conf.CELERY_TASK_RESULT_EXPIRES = timedelta(0, 3600)

	if conf.monitory_celery:
		app.conf.CELERY_SEND_EVENTS = True
		app.conf.CELERY_SEND_TASK_SENT_EVENT = True

	app.conf.CELERY_ROUTES = (SiteRouter(), AsyncTaskRouter())

	app.conf.CELERYBEAT_SCHEDULE = get_beat_schedule(conf)

	if conf.celery_error_emails:
		app.conf.CELERY_SEND_TASK_ERROR_EMAILS = True
		for k, v in conf.celery_error_emails.iteritems():
			setattr(app.conf, k, v)

	return app

def get_site_config():
	return frappe.get_site_config(sites_path=SITES_PATH)

class SiteRouter(object):
	def route_for_task(self, task, args=None, kwargs=None):
		if hasattr(frappe.local, 'site'):
			if kwargs and kwargs.get("event", "").endswith("_long"):
				return get_queue(frappe.local.site, LONGJOBS_PREFIX)
			elif kwargs and kwargs.get("async", False)==True:
				return get_queue(frappe.local.site, ASYNC_TASKS_PREFIX)
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

	schedule['sync_queues'] = {
		'task': 'frappe.tasks.sync_queues',
		'schedule': timedelta(seconds=conf.scheduler_interval or DEFAULT_SCHEDULER_INTERVAL)
	}

	return schedule

class FrappeTask(get_celery().Task):
	def run(self, *args, **kwargs):
		from frappe.utils.scheduler import log

		site = kwargs.pop('site')

		if 'async' in kwargs:
			kwargs.pop('async')

		try:
			frappe.connect(site=site)
			self.execute(*args, **kwargs)

		except Exception:
			frappe.db.rollback()

			task_logger.error(site)
			task_logger.error(frappe.get_traceback())

			log(self.__name__)
		else:
			frappe.db.commit()

		finally:
			frappe.destroy()

def celery_task(*args, **kwargs):
	return get_celery().task(*args, **kwargs)

def run_test():
	for i in xrange(30):
		test.delay(site=frappe.local.site)

@celery_task()
def test(site=None):
	time.sleep(1)
	print "task"

if __name__ == '__main__':
	app = get_celery()
	app.start()
