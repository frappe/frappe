from __future__ import unicode_literals, print_function
import redis
from rq import Connection, Queue, Worker
from rq.logutils import setup_loghandlers
from frappe.utils import cstr
from collections import defaultdict
import frappe
import os, socket, time
from frappe import _
from six import string_types

# imports - third-party imports

default_timeout = 300
queue_timeout = {
	'background': 2500,
	'long': 1500,
	'default': 300,
	'short': 300
}

redis_connection = None

def enqueue(method, queue='default', timeout=None, event=None,
	is_async=True, job_name=None, now=False, enqueue_after_commit=False, **kwargs):
	'''
		Enqueue method to be executed using a background worker

		:param method: method string or method object
		:param queue: should be either long, default or short
		:param timeout: should be set according to the functions
		:param event: this is passed to enable clearing of jobs from queues
		:param is_async: if is_async=False, the method is executed immediately, else via a worker
		:param job_name: can be used to name an enqueue call, which can be used to prevent duplicate calls
		:param now: if now=True, the method is executed via frappe.call
		:param kwargs: keyword arguments to be passed to the method
	'''
	# To handle older implementations
	if 'async' in kwargs:
		is_async = True
		del kwargs['async']

	if now or frappe.flags.in_migrate:
		return frappe.call(method, **kwargs)

	q = get_queue(queue, is_async=is_async)
	if not timeout:
		timeout = queue_timeout.get(queue) or 300
	queue_args = {
		"site": frappe.local.site,
		"user": frappe.session.user,
		"method": method,
		"event": event,
		"job_name": job_name or cstr(method),
		"is_async": is_async,
		"kwargs": kwargs
	}
	if enqueue_after_commit:
		if not frappe.flags.enqueue_after_commit:
			frappe.flags.enqueue_after_commit = []

		frappe.flags.enqueue_after_commit.append({
			"queue": queue,
			"is_async": is_async,
			"timeout": timeout,
			"queue_args":queue_args
		})
		return frappe.flags.enqueue_after_commit
	else:
		return q.enqueue_call(execute_job, timeout=timeout,
			kwargs=queue_args)

def enqueue_doc(doctype, name=None, method=None, queue='default', timeout=300,
	now=False, **kwargs):
	'''Enqueue a method to be run on a document'''
	enqueue('frappe.utils.background_jobs.run_doc_method', doctype=doctype, name=name,
		doc_method=method, queue=queue, timeout=timeout, now=now, **kwargs)

def run_doc_method(doctype, name, doc_method, **kwargs):
	getattr(frappe.get_doc(doctype, name), doc_method)(**kwargs)

def execute_job(site, method, event, job_name, kwargs, user=None, is_async=True, retry=0):
	'''Executes job in a worker, performs commit/rollback and logs if there is any error'''
	from frappe.utils.scheduler import log

	if is_async:
		frappe.connect(site)
		if os.environ.get('CI'):
			frappe.flags.in_test = True

		if user:
			frappe.set_user(user)

	if isinstance(method, string_types):
		method_name = method
		method = frappe.get_attr(method)
	else:
		method_name = cstr(method.__name__)

	try:
		method(**kwargs)

	except (frappe.db.InternalError, frappe.RetryBackgroundJobError) as e:
		frappe.db.rollback()

		if (retry < 5 and
			(isinstance(e, frappe.RetryBackgroundJobError) or
				(frappe.db.is_deadlocked() or frappe.db.is_timedout()))):
			# retry the job if
			# 1213 = deadlock
			# 1205 = lock wait timeout
			# or RetryBackgroundJobError is explicitly raised
			frappe.destroy()
			time.sleep(retry+1)

			return execute_job(site, method, event, job_name, kwargs,
				is_async=is_async, retry=retry+1)

		else:
			log(method_name, message=repr(locals()))
			raise

	except:
		frappe.db.rollback()
		log(method_name, message=repr(locals()))
		raise

	else:
		frappe.db.commit()

	finally:
		if is_async:
			frappe.destroy()

def start_worker(queue=None, quiet = False):
	'''Wrapper to start rq worker. Connects to redis and monitors these queues.'''
	with frappe.init_site():
		# empty init is required to get redis_queue from common_site_config.json
		redis_connection = get_redis_conn()

	if os.environ.get('CI'):
		setup_loghandlers('ERROR')

	with Connection(redis_connection):
		queues = get_queue_list(queue)
		logging_level = "INFO"
		if quiet:
			logging_level = "WARNING"
		Worker(queues, name=get_worker_name(queue)).work(logging_level = logging_level)

def get_worker_name(queue):
	'''When limiting worker to a specific queue, also append queue name to default worker name'''
	name = None

	if queue:
		# hostname.pid is the default worker name
		name = '{hostname}.{pid}.{queue}'.format(
			hostname=socket.gethostname(),
			pid=os.getpid(),
			queue=queue)

	return name

def get_jobs(site=None, queue=None, key='method'):
	'''Gets jobs per queue or per site or both'''
	jobs_per_site = defaultdict(list)
	for queue in get_queue_list(queue):
		q = get_queue(queue)

		for job in q.jobs:
			if job.kwargs.get('site'):
				if site is None:
					# get jobs for all sites
					jobs_per_site[job.kwargs['site']].append(job.kwargs[key])

				elif job.kwargs['site'] == site:
					# get jobs only for given site
					jobs_per_site[site].append(job.kwargs[key])

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

	kwargs = {
		'connection': get_redis_conn(),
		'async': is_async
	}

	return Queue(queue, **kwargs)

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
