# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals, absolute_import

from celery import Celery

# initiate logger
from celery.utils.log import get_task_logger
task_logger = get_task_logger(__name__)

from datetime import timedelta
import frappe
import json
import os

SITES_PATH = os.environ.get('SITES_PATH', '.')

# defaults
DEFAULT_CELERY_BROKER = "redis://localhost"
DEFAULT_CELERY_BACKEND = "redis://localhost"
DEFAULT_SCHEDULER_INTERVAL = 300
LONGJOBS_PREFIX = "longjobs@"

_app = None
def get_celery():
	global _app
	if not _app:
		conf = frappe.get_site_config(sites_path=SITES_PATH)
	
		_app = Celery('frappe', 
			broker=conf.celery_broker or DEFAULT_CELERY_BROKER, 
			backend=conf.celery_result_backend or DEFAULT_CELERY_BACKEND)
	
		setup_celery(_app, conf)
		
	return _app
	
def setup_celery(app, conf):
	app.autodiscover_tasks(frappe.get_all_apps(with_frappe=True, with_internal_apps=False,
		sites_path=SITES_PATH))
	app.conf.CELERY_TASK_SERIALIZER = 'json'
	app.conf.CELERY_ACCEPT_CONTENT = ['json']
	app.conf.CELERY_TIMEZONE = 'UTC'
	app.conf.CELERY_RESULT_SERIALIZER = 'json'
	
	if conf.celery_queue_per_site:
		app.conf.CELERY_ROUTES = (SiteRouter(),)
	
	app.conf.CELERYBEAT_SCHEDULE = get_beat_schedule(conf)

	if conf.celery_error_emails:
		app.conf.CELERY_SEND_TASK_ERROR_EMAILS = True
		for k, v in conf.celery_error_emails.iteritems():
			setattr(app.conf, k, v)
	
class SiteRouter(object):
	def route_for_task(self, task, args=None, kwargs=None):
		if hasattr(frappe.local, 'site'):
			if kwargs and kwargs.get("event", "").endswith("_long"):
				return get_queue(frappe.local.site, LONGJOBS_PREFIX)
			else:
				return get_queue(frappe.local.site)
		
		return None
		
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
	return get_celery().task(*args, **kwargs)
	
if __name__ == '__main__':
	get_celery().start()
