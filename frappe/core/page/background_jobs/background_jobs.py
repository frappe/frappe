# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from rq import Queue
from frappe.utils.background_jobs import get_redis_conn
from frappe.utils import format_datetime

colors = {
	'queued': 'orange',
	'failed': 'red',
	'started': 'green'
}

@frappe.whitelist()
def get_info():
	queues = Queue.all(get_redis_conn())
	jobs = []
	for q in queues:
		for j in q.get_jobs():
			if j.kwargs.get('site')==frappe.local.site:
				jobs.append({
					'job_name': j.kwargs.get('kwargs', {}).get('playbook_method') \
						or str(j.kwargs.get('job_name')),
					'status': j.status, 'queue': str(q.name),
					'creation': format_datetime(j.created_at),
					'color': colors[j.status]
				})

	return jobs