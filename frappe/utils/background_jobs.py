import gc
import os
import socket
import time
from collections import defaultdict
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal, NoReturn, Union
from uuid import uuid4

import redis
from redis.exceptions import BusyLoadingError, ConnectionError
from rq import Connection, Queue, Worker
from rq.exceptions import NoSuchJobError
from rq.logutils import setup_loghandlers
from rq.worker import RandomWorker, RoundRobinWorker
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

import frappe
import frappe.monitor
from frappe import _
from frappe.utils import cint, cstr, get_bench_id
from frappe.utils.commands import log
from frappe.utils.redis_queue import RedisQueue

if TYPE_CHECKING:
	from rq.job import Job


# TTL to keep RQ job logs in redis for.
RQ_JOB_FAILURE_TTL = 7 * 24 * 60 * 60  # 7 days instead of 1 year (default)
RQ_RESULTS_TTL = 10 * 60


_redis_queue_conn = None


@lru_cache
def get_queues_timeout():
	common_site_config = frappe.get_conf()
	custom_workers_config = common_site_config.get("workers", {})
	default_timeout = 300

	# Note: Order matters here
	# If no queues are specified then RQ prioritizes queues in specified order
	return {
		"short": default_timeout,
		"default": default_timeout,
		"long": 1500,
		**{
			worker: config.get("timeout", default_timeout)
			for worker, config in custom_workers_config.items()
		},
	}


def enqueue(
	method,
	queue="default",
	timeout=None,
	event=None,
	is_async=True,
	job_name=None,
	now=False,
	enqueue_after_commit=False,
	*,
	at_front=False,
	job_id=None,
	**kwargs,
) -> Union["Job", Any]:
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
	:param job_id: Assigning unique job id, which can be checked using `is_job_enqueued`
	"""
	# To handle older implementations
	is_async = kwargs.pop("async", is_async)

	if job_id:
		# namespace job ids to sites
		job_id = create_job_id(job_id)

	if not is_async and not frappe.flags.in_test:
		print(
			_(
				"Using enqueue with is_async=False outside of tests is not recommended, use now=True instead."
			)
		)

	call_directly = now or (not is_async and not frappe.flags.in_test)
	if call_directly:
		return frappe.call(method, **kwargs)

	try:
		q = get_queue(queue, is_async=is_async)
	except ConnectionError:
		if frappe.local.flags.in_migrate:
			# If redis is not available during migration, execute the job directly
			print(f"Redis queue is unreachable: Executing {method} synchronously")
			return frappe.call(method, **kwargs)

		raise

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
			{
				"queue": queue,
				"is_async": is_async,
				"timeout": timeout,
				"queue_args": queue_args,
				"job_id": job_id,
			}
		)
		return frappe.flags.enqueue_after_commit

	return q.enqueue_call(
		execute_job,
		timeout=timeout,
		kwargs=queue_args,
		at_front=at_front,
		failure_ttl=frappe.conf.get("rq_job_failure_ttl") or RQ_JOB_FAILURE_TTL,
		result_ttl=frappe.conf.get("rq_results_ttl") or RQ_RESULTS_TTL,
		job_id=job_id,
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
		**kwargs,
	)


def run_doc_method(doctype, name, doc_method, **kwargs):
	getattr(frappe.get_doc(doctype, name), doc_method)(**kwargs)


def execute_job(site, method, event, job_name, kwargs, user=None, is_async=True, retry=0):
	"""Executes job in a worker, performs commit/rollback and logs if there is any error"""
	retval = None
	if is_async:
		frappe.connect(site)
		if os.environ.get("CI"):
			frappe.flags.in_test = True

		if user:
			frappe.set_user(user)

	if isinstance(method, str):
		method_name = method
		method = frappe.get_attr(method)
	else:
		method_name = cstr(method.__name__)

	for before_job_task in frappe.get_hooks("before_job"):
		frappe.call(before_job_task, method=method_name, kwargs=kwargs, transaction_type="job")

	try:
		retval = method(**kwargs)

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
		return retval

	finally:
		for after_job_task in frappe.get_hooks("after_job"):
			frappe.call(after_job_task, method=method_name, kwargs=kwargs, result=retval)

		if is_async:
			frappe.destroy()


def start_worker(
	queue: str | None = None,
	quiet: bool = False,
	rq_username: str | None = None,
	rq_password: str | None = None,
	burst: bool = False,
	strategy: Literal["round_robin", "random"] | None = None,
) -> NoReturn | None:
	"""Wrapper to start rq worker. Connects to redis and monitors these queues."""
	DEQUEUE_STRATEGIES = {"round_robin": RoundRobinWorker, "random": RandomWorker}

	if frappe._tune_gc:
		gc.collect()
		gc.freeze()

	with frappe.init_site():
		# empty init is required to get redis_queue from common_site_config.json
		redis_connection = get_redis_conn(username=rq_username, password=rq_password)

		if queue:
			queue = [q.strip() for q in queue.split(",")]
		queues = get_queue_list(queue, build_queue_name=True)
		queue_name = queue and generate_qname(queue)

	if os.environ.get("CI"):
		setup_loghandlers("ERROR")

	set_niceness()
	WorkerKlass = DEQUEUE_STRATEGIES.get(strategy, Worker)

	with Connection(redis_connection):
		logging_level = "INFO"
		if quiet:
			logging_level = "WARNING"
		worker = WorkerKlass(queues, name=get_worker_name(queue_name))
		worker.work(
			logging_level=logging_level,
			burst=burst,
			date_format="%Y-%m-%d %H:%M:%S",
			log_format="%(asctime)s,%(msecs)03d %(message)s",
		)


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

	for _queue in get_queue_list(queue):
		q = get_queue(_queue)
		jobs = q.jobs + get_running_jobs_in_queue(q)
		for job in jobs:
			if job.kwargs.get("site"):
				# if job belongs to current site, or if all jobs are requested
				if (job.kwargs["site"] == site) or site is None:
					add_to_dict(job)
			else:
				print("No site found in job", job.__dict__)

	return jobs_per_site


def get_queue_list(queue_list=None, build_queue_name=False):
	"""Defines possible queues. Also wraps a given queue in a list after validating."""
	default_queue_list = list(get_queues_timeout())
	if queue_list:
		if isinstance(queue_list, str):
			queue_list = [queue_list]

		for queue in queue_list:
			validate_queue(queue, default_queue_list)
	else:
		queue_list = default_queue_list
	return [generate_qname(qtype) for qtype in queue_list] if build_queue_name else queue_list


def get_workers(queue=None):
	"""Returns a list of Worker objects tied to a queue object if queue is passed, else returns a list of all workers"""
	if queue:
		return Worker.all(queue=queue)
	else:
		return Worker.all(get_redis_conn())


def get_running_jobs_in_queue(queue):
	"""Returns a list of Jobs objects that are tied to a queue object and are currently running"""
	jobs = []
	workers = get_workers(queue)
	for worker in workers:
		current_job = worker.get_current_job()
		if current_job:
			jobs.append(current_job)
	return jobs


def get_queue(qtype, is_async=True):
	"""Returns a Queue object tied to a redis connection"""
	validate_queue(qtype)
	return Queue(generate_qname(qtype), connection=get_redis_conn(), is_async=is_async)


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
def get_redis_conn(username=None, password=None):
	if not hasattr(frappe.local, "conf"):
		raise Exception("You need to call frappe.init")

	elif not frappe.local.conf.redis_queue:
		raise Exception("redis_queue missing in common_site_config.json")

	global _redis_queue_conn

	cred = frappe._dict()
	if frappe.conf.get("use_rq_auth"):
		if username:
			cred["username"] = username
			cred["password"] = password
		else:
			cred["username"] = frappe.get_site_config().rq_username or get_bench_id()
			cred["password"] = frappe.get_site_config().rq_password

	elif os.environ.get("RQ_ADMIN_PASWORD"):
		cred["username"] = "default"
		cred["password"] = os.environ.get("RQ_ADMIN_PASWORD")

	try:
		if not cred:
			if not _redis_queue_conn:
				_redis_queue_conn = RedisQueue.get_connection()
			return _redis_queue_conn
		else:
			return RedisQueue.get_connection(**cred)
	except (redis.exceptions.AuthenticationError, redis.exceptions.ResponseError):
		log(
			f'Wrong credentials used for {cred.username or "default user"}. '
			"You can reset credentials using `bench create-rq-users` CLI and restart the server",
			colour="red",
		)
		raise
	except Exception:
		log(f"Please make sure that Redis Queue runs @ {frappe.get_conf().redis_queue}", colour="red")
		raise


def get_queues() -> list[Queue]:
	"""Get all the queues linked to the current bench."""
	queues = Queue.all(connection=get_redis_conn())
	return [q for q in queues if is_queue_accessible(q)]


def generate_qname(qtype: str) -> str:
	"""Generate qname by combining bench ID and queue type.

	qnames are useful to define namespaces of customers.
	"""
	if isinstance(qtype, list):
		qtype = ",".join(qtype)
	return f"{get_bench_id()}:{qtype}"


def is_queue_accessible(qobj: Queue) -> bool:
	"""Checks whether queue is relate to current bench or not."""
	accessible_queues = [generate_qname(q) for q in list(get_queues_timeout())]
	return qobj.name in accessible_queues


def enqueue_test_job():
	enqueue("frappe.utils.background_jobs.test_job", s=100)


def test_job(s):
	import time

	print("sleeping...")
	time.sleep(s)


def create_job_id(job_id: str) -> str:
	"""Generate unique job id for deduplication"""
	return f"{frappe.local.site}::{job_id}"


def is_job_enqueued(job_id: str) -> str:
	from rq.job import Job

	try:
		job = Job.fetch(create_job_id(job_id), connection=get_redis_conn())
	except NoSuchJobError:
		return False

	return job.get_status() in ("queued", "started")


BACKGROUND_PROCESS_NICENESS = 10


def set_niceness():
	"""Background processes should have slightly lower priority than web processes.

	Calling this function increments the niceness of process by configured value or default.
	Note: This function should be called only once in process' lifetime.
	"""

	conf = frappe.get_conf()
	nice_increment = BACKGROUND_PROCESS_NICENESS

	configured_niceness = conf.get("background_process_niceness")

	if configured_niceness is not None:
		nice_increment = cint(configured_niceness)

	os.nice(nice_increment)
