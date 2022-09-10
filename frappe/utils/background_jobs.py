from __future__ import print_function, unicode_literals

import os
import socket
import time
from collections import defaultdict
from functools import lru_cache
from uuid import uuid4

import redis
from redis.exceptions import BusyLoadingError, ConnectionError
from rq import Connection, Queue, Worker
from rq.logutils import setup_loghandlers
from six import string_types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

import frappe
import frappe.monitor
from frappe import _
from frappe.utils import cstr

# TTL to keep RQ job logs in redis for.
RQ_JOB_FAILURE_TTL = 7 * 24 * 60 * 60  # 7 days instead of 1 year (default)
RQ_RESULTS_TTL = 10 * 60


@lru_cache()
def get_queues_timeout():
	common_site_config = frappe.get_conf()
	custom_workers_config = common_site_config.get("workers", {})
	default_timeout = 300

	return {
		"default": default_timeout,
		"short": default_timeout,
		"long": 1500,
		**{
			worker: config.get("timeout", default_timeout)
			for worker, config in custom_workers_config.items()
		},
	}


redis_connection = None


def enqueue(
	method,
	queue="default",
	timeout=None,
	event=None,
	is_async=True,
	job_name=None,
	now=False,
	enqueue_after_commit=False,
	**kwargs
):
	"""
	Enqueue method to be executed using a background worker

	:param method: method string or method object
	:param queue: should be either long, default or short
	:param timeout: should be set according to the functions
	:param event: this is passed to enable clearing of jobs from queues
	:param is_async: if is_async=False, the method is executed immediately, else via a worker
	:param job_name: can be used to name an enqueue call, which can be used to prevent duplicate calls
	:param now: if now=True, the method is executed via frappe.call
	:param kwargs: keyword arguments to be passed to the method
	"""
	# To handle older implementations
	is_async = kwargs.pop("async", is_async)

	if now or frappe.flags.in_migrate:
		return frappe.call(method, **kwargs)

	q = get_queue(queue, is_async=is_async)
	if not timeout:
		timeout = get_queues_timeout().get(queue) or 300
	queue_args = {
		"site": frappe.local.site,
		"user": frappe.session.user,
		"method": method,
		"event": event,
		"job_name": job_name or cstr(method),
		"is_async": is_async,
		"kwargs": kwargs,
	}
	if enqueue_after_commit:
		if not frappe.flags.enqueue_after_commit:
			frappe.flags.enqueue_after_commit = []

		frappe.flags.enqueue_after_commit.append(
			{"queue": queue, "is_async": is_async, "timeout": timeout, "queue_args": queue_args}
		)
		return frappe.flags.enqueue_after_commit

	return q.enqueue_call(
		execute_job,
		timeout=timeout,
		kwargs=queue_args,
		failure_ttl=RQ_JOB_FAILURE_TTL,
		result_ttl=RQ_RESULTS_TTL,
	)


def enqueue_doc(
	doctype, name=None, method=None, queue="default", timeout=300, now=False, **kwargs
):
	"""Enqueue a method to be run on a document"""
	return enqueue(
		"frappe.utils.background_jobs.run_doc_method",
		doctype=doctype,
		name=name,
		doc_method=method,
		queue=queue,
		timeout=timeout,
		now=now,
		**kwargs
	)


def run_doc_method(doctype, name, doc_method, **kwargs):
	getattr(frappe.get_doc(doctype, name), doc_method)(**kwargs)


def execute_job(site, method, event, job_name, kwargs, user=None, is_async=True, retry=0):
	"""Executes job in a worker, performs commit/rollback and logs if there is any error"""
	if is_async:
		frappe.connect(site)
		if os.environ.get("CI"):
			frappe.flags.in_test = True

		if user:
			frappe.set_user(user)

	if isinstance(method, string_types):
		method_name = method
		method = frappe.get_attr(method)
	else:
		method_name = cstr(method.__name__)

	frappe.monitor.start("job", method_name, kwargs)
	try:
		method(**kwargs)

	except (frappe.db.InternalError, frappe.RetryBackgroundJobError) as e:
		frappe.db.rollback()

		if retry < 5 and (
			isinstance(e, frappe.RetryBackgroundJobError)
			or (frappe.db.is_deadlocked(e) or frappe.db.is_timedout(e))
		):
			# retry the job if
			# 1213 = deadlock
			# 1205 = lock wait timeout
			# or RetryBackgroundJobError is explicitly raised
			frappe.destroy()
			time.sleep(retry + 1)

			return execute_job(site, method, event, job_name, kwargs, is_async=is_async, retry=retry + 1)

		else:
			frappe.log_error(title=method_name)
			raise

	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=method_name)
		frappe.db.commit()
		print(frappe.get_traceback())
		raise

	else:
		frappe.db.commit()

	finally:
		frappe.monitor.stop()
		if is_async:
			frappe.destroy()


def start_worker(queue=None, quiet=False):
	"""Wrapper to start rq worker. Connects to redis and monitors these queues."""
	with frappe.init_site():
		# empty init is required to get redis_queue from common_site_config.json
		redis_connection = get_redis_conn()

	if os.environ.get("CI"):
		setup_loghandlers("ERROR")

	with Connection(redis_connection):
		queues = get_queue_list(queue)
		logging_level = "INFO"
		if quiet:
			logging_level = "WARNING"
		Worker(queues, name=get_worker_name(queue)).work(logging_level=logging_level)


def get_worker_name(queue):
	"""When limiting worker to a specific queue, also append queue name to default worker name"""
	name = None

	if queue:
		# hostname.pid is the default worker name
		name = "{uuid}.{hostname}.{pid}.{queue}".format(
			uuid=uuid4().hex, hostname=socket.gethostname(), pid=os.getpid(), queue=queue
		)

	return name


def get_jobs(site=None, queue=None, key="method"):
	"""Gets jobs per queue or per site or both"""
	jobs_per_site = defaultdict(list)

	def add_to_dict(job):
		if key in job.kwargs:
			jobs_per_site[job.kwargs["site"]].append(job.kwargs[key])

		elif key in job.kwargs.get("kwargs", {}):
			# optional keyword arguments are stored in 'kwargs' of 'kwargs'
			jobs_per_site[job.kwargs["site"]].append(job.kwargs["kwargs"][key])

	for queue in get_queue_list(queue):
		q = get_queue(queue)
		jobs = q.jobs + get_running_jobs_in_queue(q)
		for job in jobs:
			if job.kwargs.get("site"):
				# if job belongs to current site, or if all jobs are requested
				if (job.kwargs["site"] == site) or site is None:
					add_to_dict(job)
			else:
				print("No site found in job", job.__dict__)

	return jobs_per_site


def get_queue_list(queue_list=None):
	"""Defines possible queues. Also wraps a given queue in a list after validating."""
	default_queue_list = list(get_queues_timeout())
	if queue_list:
		if isinstance(queue_list, string_types):
			queue_list = [queue_list]

		for queue in queue_list:
			validate_queue(queue, default_queue_list)

		return queue_list

	else:
		return default_queue_list


def get_workers(queue):
	"""Returns a list of Worker objects tied to a queue object"""
	return Worker.all(queue=queue)


def get_running_jobs_in_queue(queue):
	"""Returns a list of Jobs objects that are tied to a queue object and are currently running"""
	jobs = []
	workers = get_workers(queue)
	for worker in workers:
		current_job = worker.get_current_job()
		if current_job:
			jobs.append(current_job)
	return jobs


def get_queue(queue, is_async=True):
	"""Returns a Queue object tied to a redis connection"""
	validate_queue(queue)
	return Queue(queue, connection=get_redis_conn(), is_async=is_async)


def validate_queue(queue, default_queue_list=None):
	if not default_queue_list:
		default_queue_list = list(get_queues_timeout())

	if queue not in default_queue_list:
		frappe.throw(_("Queue should be one of {0}").format(", ".join(default_queue_list)))


@retry(
	retry=retry_if_exception_type(BusyLoadingError) | retry_if_exception_type(ConnectionError),
	stop=stop_after_attempt(10),
	wait=wait_fixed(1),
)
def get_redis_conn():
	if not hasattr(frappe.local, "conf"):
		raise Exception("You need to call frappe.init")

	elif not frappe.local.conf.redis_queue:
		raise Exception("redis_queue missing in common_site_config.json")

	global redis_connection

	if not redis_connection:
		redis_connection = redis.from_url(frappe.local.conf.redis_queue)

	return redis_connection


def enqueue_test_job():
	enqueue("frappe.utils.background_jobs.test_job", s=100)


def test_job(s):
	import time

	print("sleeping...")
	time.sleep(s)
