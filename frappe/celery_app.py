# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
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
DEFAULT_CELERY_BACKEND = None
DEFAULT_SCHEDULER_INTERVAL = 300

_app = None
def get_celery():
	global _app
	if not _app:
		frappe.local.sites_path = SITES_PATH
		conf = frappe.get_site_config()
	
		_app = Celery('frappe', 
			broker=conf.celery_broker or DEFAULT_CELERY_BROKER, 
			backend=conf.celery_result_backend or DEFAULT_CELERY_BACKEND)
	
		setup_celery(_app, conf)
	
	return _app
	
def setup_celery(app, conf):
	app.autodiscover_tasks(frappe.get_all_apps(with_frappe=True, with_internal_apps=False))
	app.conf.CELERY_TASK_SERIALIZER = 'json'
	app.conf.CELERY_ACCEPT_CONTENT = ['json']
	app.conf.CELERY_ROUTES = (SiteRouter(),)
	app.conf.CELERYBEAT_SCHEDULE = get_beat_schedule(conf)
	app.conf.CELERY_TIMEZONE = 'UTC'
	
class SiteRouter(object):
	def route_for_task(self, task, args=None, kwargs=None):
		if hasattr(frappe.local, 'site'):
			return {
				'queue': frappe.local.site
			}
		return None
	
def get_beat_schedule(conf):
	return {
	    'scheduler': {
	        'task': 'frappe.tasks.enqueue_scheduler_events',
	        'schedule': timedelta(seconds=conf.scheduler_interval or DEFAULT_SCHEDULER_INTERVAL)
	    },
	    'sync_queues': {
	        'task': 'frappe.tasks.sync_queues',
	        'schedule': timedelta(seconds=conf.scheduler_interval or DEFAULT_SCHEDULER_INTERVAL)
	    }
	}
	
def celery_task(*args, **kwargs):
	return get_celery().task(*args, **kwargs)
	
if __name__ == '__main__':
	get_celery().start()
