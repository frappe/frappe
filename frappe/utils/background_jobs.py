from __future__ import unicode_literals, print_function
import redis
from rq import Connection, Queue, Worker
from rq.logutils import setup_loghandlers
from frappe.utils import cstr
from collections import defaultdict
import frappe
import os, socket
from frappe import _
from six import string_types
from types import FunctionType, MethodType
from pickle import dumps as pickle_dumps
from gevent.pool import Pool as GeventPool
from uuid import uuid4
from time import perf_counter
import frappe.monitor
from frappe import _dict

# imports - third-party imports

default_timeout = 300
queue_timeout = {
	'background': 2500,
	'long': 1500,
	'default': 300,
	'short': 300
}

redis_connection = None

def enqueue(method, queue='default', timeout=None, event=None, monitor=False, set_user=None,
	method_name=None, job_name=None, now=False, enqueue_after_commit=False,
	sessionless=False, partition_key=None, **kwargs):
	'''
		Enqueue method to be executed using a background worker

		:param method: method string or method object
		:param queue: should be either long, default or short
		:param timeout: should be set according to the functions
		:param event: this is passed to enable clearing of jobs from queues
		:param job_name: can be used to name an enqueue call, which can be used to prevent duplicate calls
		:param now: if now=True, the method is executed via frappe.call
		:param kwargs: keyword arguments to be passed to the method
	'''
	kwargs.pop('async', None)
	kwargs.pop('is_async', None)
	if not queue:
		queue = 'default'

	if now or frappe.flags.in_migrate or frappe.flags.in_install_app:
		if isinstance(method, str):
			method = frappe.get_attr(method)
		return method(**kwargs)

	if not method_name:
		if type(method) in (FunctionType, MethodType):
			method_name = f'{method.__module__}.{method.__name__}'
		else:
			method_name = str(method)

	queue_args = {
		"site": frappe.local.site,
		"user": set_user or frappe.session.user,
		"method": method,
		"method_name": method_name,
		"event": event,
		"job_name": job_name or cstr(method),
		"kwargs": kwargs,
		"partition_key": partition_key,
		"queue": 'kafka' if partition_key else queue,
		"request_id": frappe.flags.request_id,
		"sessionless": sessionless,
	}

	if enqueue_after_commit:
		frappe.db.run_after_commit(enqueue_to_redis, queue_args)
	else:
		enqueue_to_redis(queue_args)

def enqueue_to_redis(kwargs):
	pickled = pickle_dumps(kwargs)
	# compressed = compress(pickled)
	conn = get_redis_conn()
	queue_name = f'frappe:bg:queue:{kwargs["queue"]}'
	conn.lpush(queue_name, pickled)

def enqueue_doc(doctype, name=None, method=None, queue='default', timeout=300,
	now=False, **kwargs):
	'''Enqueue a method to be run on a document'''
	return enqueue('frappe.utils.background_jobs.run_doc_method', doctype=doctype, name=name,
		doc_method=method, queue=queue, timeout=timeout, now=now, **kwargs)

def run_doc_method(doctype, name, doc_method, **kwargs):
	getattr(frappe.get_doc(doctype, name), doc_method)(**kwargs)

class Task(object):
	__slots__ = ['id', 'site', 'method', 'user', 'method_name', 'kwargs', 'queue',
				'request_id', 'flags']

	pool = GeventPool(50)

	def __init__(self, site, method, user, method_name, kwargs, queue,
		request_id, **flags):
		self.id = str(uuid4())
		self.site = site
		self.method = method
		self.user = user

		if not method_name:
			if isinstance(method, string_types):
				method_name = method
			else:
				method_name = f'{self.method.__module__}.{self.method.__name__}'

		self.method_name = method_name
		self.kwargs = kwargs
		self.queue = queue
		self.request_id = request_id
		self.flags = _dict(flags)

	def process_task(self):
		return self.pool.spawn(fastrunner, self)

def fastrunner(task, throws=True, before_commit=None):
	frappe.init(site=task.site)
	frappe.flags.request_id = task.request_id
	frappe.flags.task_id = str(uuid4())
	frappe.flags.runner_type = f'fastrunner-{task.queue}'
	frappe.connect()
	frappe.local.lang = frappe.db.get_default('lang')
	log = frappe.logger('bg_info')
	log.info({
		'method': task.method_name,
		'pool_size': len(task.pool),
		'stage': 'Executing',
	})
	try:
		if isinstance(task.method, string_types):
			task.method = frappe.get_attr(task.method)
		if task.user:
			frappe.set_user(task.user)
		else:
			frappe.set_user('Administrator')
		start_time = perf_counter()
		task.method(**task.kwargs)
		if before_commit:
			before_commit(task)
		end_time = perf_counter()
		frappe.db.commit()
		log.info({
			'turnaround_time': end_time - start_time,
			'python_time': (end_time - start_time) - frappe.local.sql_time,
			'sql_time': frappe.local.sql_time,
			'method': task.method_name,
			'pool_size': len(task.pool),
			'stage': 'Completed',
		})
	except Exception:
		frappe.db.rollback()
		traceback = frappe.get_traceback()
		log.info({
			'sql_time': frappe.local.sql_time,
			'method': task.method_name,
			'pool_size': len(task.pool),
			'stage': 'Failed',
			'traceback': traceback,
		})
		frappe.log_error(title=task.method_name, message=traceback)
	finally:
		frappe.destroy()

def get_worker_name(queue):
	'''When limiting worker to a specific queue, also append queue name to default worker name'''
	name = None

	if queue:
		# hostname.pid is the default worker name
		name = '{uuid}.{hostname}.{pid}.{queue}'.format(
			uuid=uuid4().hex,
			hostname=socket.gethostname(),
			pid=os.getpid(),
			queue=queue)

	return name

def get_jobs(site=None, queue=None, key='method'):
	'''Gets jobs per queue or per site or both'''
	jobs_per_site = defaultdict(list)

	def add_to_dict(job):
		if key in job.kwargs:
			jobs_per_site[job.kwargs['site']].append(job.kwargs[key])

		elif key in job.kwargs.get('kwargs', {}):
			# optional keyword arguments are stored in 'kwargs' of 'kwargs'
			jobs_per_site[job.kwargs['site']].append(job.kwargs['kwargs'][key])

	for queue in get_queue_list(queue):
		q = get_queue(queue)

		for job in q.jobs:
			if job.kwargs.get('site'):
				if site is None:
					add_to_dict(job)

				elif job.kwargs['site'] == site:
					add_to_dict(job)

			else:
				print('No site found in job', job.__dict__)

	return jobs_per_site

def get_queue_list(queue_list=None):
	'''Defines possible queues. Also wraps a given queue in a list after validating.'''
	default_queue_list = list(queue_timeout)
	if queue_list:
		if isinstance(queue_list, string_types):
			queue_list = [queue_list]

		for queue in queue_list:
			validate_queue(queue, default_queue_list)

		return queue_list

	else:
		return default_queue_list

def get_queue(queue, is_async=True):
	'''Returns a Queue object tied to a redis connection'''
	validate_queue(queue)
	return Queue(queue, connection=get_redis_conn(), is_async=is_async)

def validate_queue(queue, default_queue_list=None):
	if not default_queue_list:
		default_queue_list = list(queue_timeout)

	if queue not in default_queue_list:
		frappe.throw(_("Queue should be one of {0}").format(', '.join(default_queue_list)))

def get_redis_conn():
	if not hasattr(frappe.local, 'conf'):
		raise Exception('You need to call frappe.init')

	elif not frappe.local.conf.redis_queue:
		raise Exception('redis_queue missing in common_site_config.json')

	global redis_connection

	if not redis_connection:
		redis_connection = redis.from_url(frappe.local.conf.redis_queue)

	return redis_connection

def enqueue_test_job():
	enqueue('frappe.utils.background_jobs.test_job', s=100)

def test_job(s):
	import time
	print('sleeping...')
	time.sleep(s)
