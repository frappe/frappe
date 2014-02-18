from __future__ import absolute_import
from celery import Celery
from datetime import timedelta
import frappe
import json
import os

SITES_PATH = os.environ.get('SITES_PATH', '.')

def get_conf():
	if hasattr(frappe.local, 'initialised'):
		return frappe.local.conf
	with open(os.path.join(SITES_PATH, 'site_config.json')) as f:
		return json.load(f)

def get_app():
	conf = get_conf()
	frappe.local.sites_path = SITES_PATH
	app = Celery('frappe', 
			broker=conf['celery_broker'], 
			backend=conf['celery_result_backend'])
	app.autodiscover_tasks(frappe.get_all_apps(with_frappe=True, with_internal_apps=False))
	app.conf.CELERY_TASK_SERIALIZER = 'json'
	app.conf.CELERYBEAT_SCHEDULE = {
	    'scheduler': {
		        'task': 'frappe.tasks.enqueue_scheduler_events',
		        'schedule': timedelta(seconds=conf['scheduler_interval'])
		    },
	}

	app.conf.CELERY_TIMEZONE = 'UTC'
	return app

app = get_app()

if __name__ == '__main__':
	app.start()
