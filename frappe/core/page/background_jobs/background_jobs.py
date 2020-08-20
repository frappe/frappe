# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint
from frappe.utils.background_jobs import get_redis_conn
from frappe.utils.scheduler import is_scheduler_inactive
from frappe import _

colors = {
	'queued': 'orange',
	'failed': 'red',
	'started': 'blue',
	'finished': 'green'
}

@frappe.whitelist()
def get_info(show_failed=False):
	conn = get_redis_conn()
	queues = {key.rsplit(':', -1)[-1] for key in conn.keys('frappe:bg:queue:*')}
	queues.add('short')
	queues.add('long')
	queues.add('default')

	info = {
		'pending_jobs': get_queue_info(queues),
	}
	print(info)
	return info

def get_queue_info(queues):
	conn = get_redis_conn()
	queue_info = {}
	for queue in queues:
		queue_name = f'frappe:bg:queue:{queue}'
		counter_name = f'frappe:bg:counter:{queue}'
		queue_info[queue] = [
			conn.llen(queue_name),
		] + [cint(row) for row in conn.mget([
			f'{counter_name}:total',
			f'{counter_name}:success',
			f'{counter_name}:failed'
		])]
	return queue_info

@frappe.whitelist()
def get_scheduler_status():
	if is_scheduler_inactive():
		return [_("Inactive"), "red"]
	return [_("Active"), "green"]
