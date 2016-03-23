from __future__ import unicode_literals
from redis import Redis
from rq import Connection, Queue, Worker
from frappe.utils import cstr
from collections import defaultdict
from urlparse import urlparse
import os
import frappe


logger = frappe.get_logger(__name__)
SITES_PATH = os.environ.get('SITES_PATH', '.')

def enqueue(method, queue, timeout, event, **kwargs):
	"""queue should be either long, high or short timeout should be set accoridngly"""
	q = get_queue(queue)
	q.enqueue_call(execute_job, timeout=timeout, 
		kwargs={
			"site": frappe.local.site,
			"method": method,
			"event": event,
			"kwargs":kwargs
		})


def get_queue_list(queue=None):
	queue_list = ['long', 'default', 'short']
	if queue:
		if queue not in queue_list:
			frappe.throw("Queue should be one of {0}".format(', '.join(queue_list)))
		else:
			return [queue]
	else:
		return queue_list


def get_jobs(site=None, queue=None):
	jobs_per_site = defaultdict(list)
	for queue in get_queue_list(queue):
		q = get_queue(queue)

		for job in q.jobs:
			if site is None:
				jobs_per_site[job.kwargs['site']].append(job.kwargs['method'])
			
			elif job.kwargs['site'] == site:
					jobs_per_site[site].append(job.kwargs['method'])
	return jobs_per_site


def execute_job(site, method, kwargs):
	from frappe.utils.scheduler import log
	frappe.connect(site)

	if isinstance(method, basestring):
		method_name = method
		method = frappe.get_attr(method)
	else:
		method_name = cstr(method)

	try:
		method(**kwargs)
	except:
		frappe.db.rollback()
		log(method_name)
	else:
		frappe.db.commit()
	finally:
		frappe.destroy()


def start_worker():
	with Connection(get_redis_conn()):
		qs = ['short', 'default', 'long']
		Worker(qs).work()


def get_queue(queue):
	return Queue(queue, connection=get_redis_conn())


def get_redis_conn():
	hostname, port = get_redis_config()
	return Redis(hostname, port)


def get_redis_config():
	conf = frappe.local.conf

	try:
		url = urlparse(conf.redis_queue).hostname
		port = urlparse(conf.redis_queue).port
		return url, port
	except:
		raise Exception('redis_queue missing in common_site_config.json')