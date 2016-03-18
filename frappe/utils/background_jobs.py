from __future__ import unicode_literals
from redis import Redis, from_url
from rq import Connection, Queue, Worker
from collections import defaultdict
from frappe.utils import cstr
from urlparse import urlparse
import os
import frappe


logger = frappe.get_logger(__name__)
SITES_PATH = os.environ.get('SITES_PATH', '.')

def enqueue(method, queue, timeout, **kwargs):
	"""queue should be either long, high or short
	timeout should be set accoridngly"""
	conf = get_site_config()
	try:
		url = urlparse(conf.redis_queue).hostname
		port = urlparse(conf.redis_queue).port
	except:
		raise Exception('Redis configuration missing for Site: {0}'.format(frappe.local.site))

	q = Queue(queue, connection=Redis(url, port))
	q.enqueue_call(execute_job, timeout=timeout, args=(frappe.local.site, method, kwargs))

def get_jobs():
	jobs_per_site = defaultdict(list)
	queue_list = ['long', 'default', 'short']
	for queue in queue_list:
		q = Queue(queue, connection=Redis())
		for job in q.jobs:
			jobs_per_site[job.args[0]].append(job.args[1])
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
	with Connection():
		qs = ['short' , 'default', 'long']
		Worker(qs).work()

def get_site_config():
	return frappe.get_site_config(sites_path=SITES_PATH)
