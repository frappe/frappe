import os
import random
import signal
import socket
import time
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from functools import lru_cache
from threading import Thread
from typing import Any, NoReturn
from uuid import uuid4

import redis
from redis.exceptions import BusyLoadingError, ConnectionError
from rq import Callback, Queue, Worker
from rq.defaults import DEFAULT_WORKER_TTL
from rq.exceptions import InvalidJobOperation, NoSuchJobError
from rq.job import Job, JobStatus
from rq.logutils import setup_loghandlers
from rq.timeouts import JobTimeoutException
from rq.worker import DequeueStrategy, StopRequested, WorkerStatus
from rq.worker_pool import WorkerPool
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

import frappe
import frappe.monitor
from frappe import _
from frappe.utils import CallbackManager, cint, get_bench_id, get_sites
from frappe.utils.caching import site_cache
from frappe.utils.commands import log
from frappe.utils.data import sbool
from frappe.utils.redis_queue import RedisQueue

# TTL to keep RQ job logs in redis for.
RQ_JOB_FAILURE_TTL = 7 * 24 * 60 * 60  # 7 days instead of 1 year (default)
RQ_FAILED_JOBS_LIMIT = 1000  # Only keep these many recent failed jobs around
RQ_RESULTS_TTL = 10 * 60

RQ_MAX_JOBS = 5000  # Restart NOFORK workers after every N number of jobs
RQ_MAX_JOBS_JITTER = 50  # Random difference in max jobs to avoid restarting at same time

MAX_QUEUED_JOBS = 500  # frappe.enqueue will start failing when these many jobs exist in queue.
# When too many jobs are pending in queue, order can be selectively flipped to LIFO to give better
# response latencies to interactive jobs.
QUEUE_STARVATION_THRESHOLD = 16


_redis_queue_conn = None


@lru_cache
def get_queues_timeout() -> dict[str, int]:
	"""
	Method returning a mapping of queue name to timeout for that queue

	:return: Dictionary of queue name to timeout
	"""
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
			worker: config.get("timeout", default_timeout) for worker, config in custom_workers_config.items()
		},
	}


def enqueue(
	method: str | Callable,
	queue: str = "default",
	timeout: int | None = None,
	event: str | None = None,
	is_async: bool = True,
	job_name: str | None = None,
	now: bool = False,
	enqueue_after_commit: bool = False,
	*,
	on_success: Callable | None = None,
	on_failure: Callable | None = None,
	at_front: bool = False,
	job_id: str | None = None,
	deduplicate=False,
	at_front_when_starved=False,
	**kwargs,
) -> Job | Any:
	"""
	Enqueue method to be executed using a background worker

	:param method: method string or method object
	:param queue: should be either long, default or short
	:param timeout: should be set according to the functions
	:param event: this is passed to enable clearing of jobs from queues
	:param is_async: if is_async=False, the method is executed immediately, else via a worker
	:param job_name: [DEPRECATED] can be used to name an enqueue call, which can be used to prevent
	duplicate calls
	:param now: if now=True, the method is executed via frappe.call()
	:param enqueue_after_commit: if True, the job will be enqueued after the current transaction is
	committed
	:param on_success: Success callback
	:param on_failure: Failure callback
	:param at_front: Enqueue the job at the front of the queue or not
	:param kwargs: keyword arguments to be passed to the method
	:param deduplicate: do not re-queue job if it's already queued, requires job_id.
	:param job_id: Assigning unique job id, which can be checked using `is_job_enqueued`
	:param at_front_when_starved: If the queue appears to be starved then new jobs are
	automatically inserted in LIFO fashion.
	"""
	# To handle older implementations
	is_async = kwargs.pop("async", is_async)

	if deduplicate:
		if not job_id:
			frappe.throw(_("`job_id` paramater is required for deduplication."))
		job = get_job(job_id)
		if job and job.get_status(refresh=False) in (JobStatus.QUEUED, JobStatus.STARTED):
			frappe.logger().error(f"Not queueing job {job.id} because it is in queue already")
			return
		elif job:
			# delete job to avoid argument issues related to job args
			# https://github.com/rq/rq/issues/793
			job.delete()

		# If job exists and is completed then delete it before re-queue

	# namespace job ids to sites
	job_id = create_job_id(job_id)

	if job_name:
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown", "v17", "Using enqueue with `job_name` is deprecated, use `job_id` instead."
		)

	if not is_async and not frappe.in_test:
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown",
			"v17",
			"Using enqueue with is_async=False outside of tests is not recommended, use now=True instead.",
		)

	call_directly = now or (not is_async and not frappe.in_test)
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

	_check_queue_size(q)

	if not timeout:
		timeout = get_queues_timeout().get(queue) or 300

	# Prepare a more readable name than <function $name at $address>
	if isinstance(method, Callable):
		method_name = f"{method.__module__}.{method.__qualname__}"
	else:
		method_name = method

	queue_args = {
		"site": frappe.local.site,
		"user": frappe.session.user,
		"method": method,
		"event": event,
		"job_name": job_name or method_name,
		"is_async": is_async,
		"kwargs": kwargs,
	}

	on_failure = on_failure or truncate_failed_registry

	if at_front_when_starved and q.count > QUEUE_STARVATION_THRESHOLD:
		at_front = True

	def enqueue_call():
		return q.enqueue_call(
			"frappe.utils.background_jobs.execute_job",
			on_success=Callback(func=on_success) if on_success else None,
			on_failure=Callback(func=on_failure),
			timeout=timeout,
			kwargs=queue_args,
			at_front=at_front,
			failure_ttl=frappe.conf.get("rq_job_failure_ttl") or RQ_JOB_FAILURE_TTL,
			result_ttl=frappe.conf.get("rq_results_ttl") or RQ_RESULTS_TTL,
			job_id=job_id,
		)

	if enqueue_after_commit:
		frappe.db.after_commit.add(enqueue_call)
		return

	return enqueue_call()


def enqueue_doc(doctype, name=None, method=None, queue="default", timeout=300, now=False, **kwargs):
	"""
	Enqueue a method to be run on a document

	:param doctype: DocType of the document on which you want to run the event
	:param name: Name of the document on which you want to run the event
	:param method: method string or method object
	:param queue: (optional) should be either long, default or short
	:param timeout: (optional) should be set according to the functions
	:param kwargs: keyword arguments to be passed to the method
	"""
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
		frappe.init(site, force=True)
		frappe.connect()
		if os.environ.get("CI"):
			from frappe.tests.utils import toggle_test_mode

			toggle_test_mode(True)

		if user:
			frappe.set_user(user)

	if isinstance(method, str):
		method_name = method
		method = frappe.get_attr(method)
	else:
		method_name = f"{method.__module__}.{method.__qualname__}"

	frappe.local.job = frappe._dict(
		site=site,
		method=method_name,
		job_name=job_name,
		kwargs=kwargs,
		user=user,
		after_job=CallbackManager(),
	)

	for before_job_task in frappe.get_hooks("before_job"):
		frappe.call(before_job_task, method=method_name, kwargs=kwargs, transaction_type="job")

	try:
		retval = method(**kwargs)

	except (frappe.db.InternalError, frappe.RetryBackgroundJobError) as e:
		frappe.db.rollback(chain=True)

		if retry < 5 and (
			isinstance(e, frappe.RetryBackgroundJobError)
			or (frappe.db.is_deadlocked(e) or frappe.db.is_timedout(e))
		):
			# retry the job if
			# 1213 = deadlock
			# 1205 = lock wait timeout
			# or RetryBackgroundJobError is explicitly raised
			frappe.job.after_job.reset()
			frappe.destroy()
			time.sleep(retry + 1)

			return execute_job(site, method, event, job_name, kwargs, is_async=is_async, retry=retry + 1)

		else:
			frappe.log_error(title=method_name)
			raise

	except Exception as e:
		frappe.db.rollback(chain=True)
		frappe.log_error(title=method_name)
		frappe.monitor.add_data_to_monitor(exception=e.__class__.__name__)
		frappe.db.commit(chain=True)
		print(frappe.get_traceback())
		raise

	else:
		frappe.db.commit(chain=True)
		return retval

	finally:
		if not hasattr(frappe.local, "site"):
			frappe.init(site, force=True)
			frappe.connect()
		for after_job_task in frappe.get_hooks("after_job"):
			frappe.call(after_job_task, method=method_name, kwargs=kwargs, result=retval)
		frappe.local.job.after_job.run()

		if is_async:
			frappe.destroy()


def start_worker(
	queue: str | None = None,
	quiet: bool = False,
	rq_username: str | None = None,
	rq_password: str | None = None,
	burst: bool = False,
	strategy: DequeueStrategy | None = DequeueStrategy.DEFAULT,
) -> NoReturn:  # pragma: no cover
	"""Wrapper to start rq worker. Connects to redis and monitors these queues."""

	if not strategy:
		strategy = DequeueStrategy.DEFAULT

	_start_sentry()

	with frappe.init_site():
		# empty init is required to get redis_queue from common_site_config.json
		redis_connection = get_redis_conn(username=rq_username, password=rq_password)

		if queue:
			queue = [q.strip() for q in queue.split(",")]
		queues = get_queue_list(queue, build_queue_name=True)

	if os.environ.get("CI"):
		setup_loghandlers("ERROR")

	set_niceness()

	logging_level = "INFO"
	if quiet:
		logging_level = "WARNING"

	worker = Worker(queues, connection=redis_connection)
	worker.work(
		logging_level=logging_level,
		burst=burst,
		date_format="%Y-%m-%d %H:%M:%S",
		log_format="%(asctime)s,%(msecs)03d %(message)s",
		dequeue_strategy=strategy,
		with_scheduler=False,
	)


class FrappeWorker(Worker):
	def work(self, *args, **kwargs):
		self.start_frappe_scheduler()
		kwargs["with_scheduler"] = False  # Always disable RQ scheduler
		return super().work(*args, **kwargs)

	def run_maintenance_tasks(self, *args, **kwargs):
		"""Attempt to start a scheduler in case the worker doing scheduling died."""
		self.start_frappe_scheduler()
		return super().run_maintenance_tasks(*args, **kwargs)

	def start_frappe_scheduler(self):
		from frappe.utils.scheduler import start_scheduler

		Thread(target=start_scheduler, daemon=True).start()


class FrappeWorkerNoFork(FrappeWorker):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.push_exc_handler(self.no_fork_exception_handler)

	def work(self, *args, **kwargs):
		kwargs["max_jobs"] = RQ_MAX_JOBS + random.randint(0, RQ_MAX_JOBS_JITTER)
		return super().work(*args, **kwargs)

	def execute_job(self, job: "Job", queue: "Queue"):
		"""Execute job in same thread/process, do not fork()"""
		self.prepare_execution(job)
		self.perform_job(job, queue)
		self.set_state(WorkerStatus.IDLE)

	def no_fork_exception_handler(self, job, exc_type, exc_value, traceback):
		if isinstance(exc_value, JobTimeoutException):
			# This is done to avoid polluting global state from partial executions.
			# More such cases MIGHT surface and this is where they should be handled.
			raise StopRequested

	def get_heartbeat_ttl(self, job: "Job") -> int:
		if job.timeout == -1:
			return DEFAULT_WORKER_TTL
		else:
			return int(job.timeout or DEFAULT_WORKER_TTL) + 60

	def kill_horse(self, sig=signal.SIGKILL):
		# Horse = self when we are not forking
		os.kill(os.getpid(), sig)


def start_worker_pool(
	queue: str | None = None,
	num_workers: int = 1,
	quiet: bool = False,
	burst: bool = False,
) -> NoReturn:
	"""Start worker pool with specified number of workers.

	WARNING: This feature is considered "EXPERIMENTAL".
	"""

	_start_sentry()

	# If gc.freeze is done then importing modules before forking allows us to share the memory
	import frappe.database.query  # sqlparse and indirect imports
	import frappe.query_builder  # pypika
	import frappe.utils  # common utils
	import frappe.utils.safe_exec
	import frappe.utils.scheduler
	import frappe.utils.typing_validations  # any whitelisted method uses this
	import frappe.website.path_resolver  # all the page types and resolver
	# end: module pre-loading

	with frappe.init_site():
		redis_connection = get_redis_conn()

		if queue:
			queue = [q.strip() for q in queue.split(",")]
		queues = get_queue_list(queue, build_queue_name=True)

	if os.environ.get("CI"):
		setup_loghandlers("ERROR")

	set_niceness()
	logging_level = "INFO"
	if quiet:
		logging_level = "WARNING"

	# TODO: Make this true by default eventually. It's limited to RQ WorkerPool
	no_fork = sbool(os.environ.get("FRAPPE_BACKGROUND_WORKERS_NOFORK", False))

	worker_klass = FrappeWorkerNoFork if no_fork else FrappeWorker
	pool = WorkerPool(
		queues=queues,
		connection=redis_connection,
		num_workers=num_workers,
		worker_class=worker_klass,
	)
	pool.start(logging_level=logging_level, burst=burst)


def get_worker_name(queue):
	"""When limiting worker to a specific queue, also append queue name to default worker name"""
	name = None

	if queue:
		# hostname.pid is the default worker name
		name = f"{uuid4().hex}.{socket.gethostname()}.{os.getpid()}.{queue}"

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
	"""Return a list of Worker objects tied to a queue object if queue is passed, else return a list of all workers."""
	if queue:
		return Worker.all(queue=queue)
	else:
		return Worker.all(get_redis_conn())


def get_running_jobs_in_queue(queue):
	"""Return a list of Jobs objects that are tied to a queue object and are currently running."""
	jobs = []
	workers = get_workers(queue)
	for worker in workers:
		current_job = worker.get_current_job()
		if current_job:
			jobs.append(current_job)
	return jobs


def get_queue(qtype: str, is_async: bool = True) -> Queue:
	"""
	Return a Queue object tied to a redis connection.

	:param qtype: Queue type, should be either long, default or short
	:param is_async: Whether the job should be executed asynchronously or in the same process
	:return: Queue object
	"""
	validate_queue(qtype)
	return Queue(generate_qname(qtype), connection=get_redis_conn(), is_async=is_async)


def validate_queue(queue: str, default_queue_list: list | None = None) -> None:
	"""
	Validates if the queue is in the list of default queues.

	:param queue: The queue to be validated
	:param default_queue_list: Optionally, a custom list of queues to validate against
	:return:
	"""
	if not default_queue_list:
		default_queue_list = list(get_queues_timeout())

	if queue not in default_queue_list:
		frappe.throw(_("Queue should be one of {0}").format(", ".join(default_queue_list)))


@retry(
	retry=retry_if_exception_type((BusyLoadingError, ConnectionError)),
	stop=stop_after_attempt(5),
	wait=wait_fixed(1),
	reraise=True,
)
def get_redis_conn(username=None, password=None):
	if not hasattr(frappe.local, "conf"):
		raise Exception("You need to call frappe.init")

	conf = frappe.get_site_config()
	if not conf.redis_queue:
		raise Exception("redis_queue missing in common_site_config.json")

	global _redis_queue_conn

	cred = frappe._dict()
	if conf.get("use_rq_auth"):
		if username:
			cred["username"] = username
			cred["password"] = password
		else:
			cred["username"] = conf.rq_username or get_bench_id()
			cred["password"] = conf.rq_password

	elif os.environ.get("RQ_ADMIN_PASWORD"):
		cred["username"] = "default"
		cred["password"] = os.environ.get("RQ_ADMIN_PASWORD")

	try:
		if not cred:
			return get_redis_connection_without_auth()
		else:
			return RedisQueue.get_connection(**cred)
	except redis.exceptions.AuthenticationError:
		log(
			f'Wrong credentials used for {cred.username or "default user"}. '
			"You can reset credentials using `bench create-rq-users` CLI and restart the server",
			colour="red",
		)
		raise
	except Exception as e:
		log(
			f"Please make sure that Redis Queue runs @ {frappe.get_conf().redis_queue}. Redis reported error: {e!s}",
			colour="red",
		)
		raise


def get_redis_connection_without_auth():
	global _redis_queue_conn

	if not _redis_queue_conn:
		_redis_queue_conn = RedisQueue.get_connection()
	return _redis_queue_conn


def get_queues(connection=None) -> list[Queue]:
	"""Get all the queues linked to the current bench."""
	queues = Queue.all(connection=connection or get_redis_conn())
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


def create_job_id(job_id: str | None = None) -> str:
	"""
	Generate unique job id for deduplication

	:param job_id: Optional job id, if not provided, a UUID is generated for it
	:return: Unique job id, namespaced by site
	"""

	if not job_id:
		job_id = str(uuid4())
	else:
		job_id = job_id.replace(":", "|")
	return f"{frappe.local.site}||{job_id}"


def is_job_enqueued(job_id: str) -> bool:
	return get_job_status(job_id) in (JobStatus.QUEUED, JobStatus.STARTED)


def get_job_status(job_id: str) -> JobStatus | None:
	"""Get RQ job status, returns None if job is not found."""
	if job := get_job(job_id):
		return job.get_status(refresh=False)


def get_job(job_id: str) -> Job | None:
	try:
		return Job.fetch(create_job_id(job_id), connection=get_redis_conn())
	except (NoSuchJobError, InvalidJobOperation):
		return None


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


def truncate_failed_registry(job, connection, type, value, traceback):
	"""Ensures that number of failed jobs don't exceed specified limits."""
	from frappe.utils import create_batch

	conf = frappe.conf if frappe.conf else frappe.get_conf(site=job.kwargs.get("site"))
	limit = (conf.get("rq_failed_jobs_limit") or RQ_FAILED_JOBS_LIMIT) - 1

	for queue in get_queues(connection=connection):
		fail_registry = queue.failed_job_registry
		failed_jobs = fail_registry.get_job_ids()[limit:]
		for job_ids in create_batch(failed_jobs, 100):
			for job_obj in Job.fetch_many(job_ids=job_ids, connection=connection):
				job_obj and fail_registry.remove(job_obj, delete_job=True)


def _check_queue_size(q: Queue):
	max_jobs = cint(frappe.conf.max_queued_jobs) or MAX_QUEUED_JOBS
	# Workaround for arbitrarily sized benches,
	# TODO: Some concept of site-based fairness on consumption of queue
	max_jobs += _site_count() * 50

	if cint(q.count) >= max_jobs:
		primary_action = {
			"label": "Monitor System Health",
			"client_action": "frappe.set_route",
			"args": ["Form", "System Health Report"],
		}
		frappe.throw(
			_("Too many queued background jobs ({0}). Please retry after some time.").format(max_jobs),
			title=_("Queue Overloaded"),
			exc=frappe.QueueOverloaded,
			primary_action=primary_action if frappe.has_permission("System Health Report") else None,
		)


@site_cache(ttl=10 * 60)
def _site_count() -> int:
	return len(get_sites())


def _start_sentry():
	sentry_dsn = os.getenv("FRAPPE_SENTRY_DSN")
	if not sentry_dsn:
		return

	import sentry_sdk
	from sentry_sdk.integrations.argv import ArgvIntegration
	from sentry_sdk.integrations.atexit import AtexitIntegration
	from sentry_sdk.integrations.dedupe import DedupeIntegration
	from sentry_sdk.integrations.excepthook import ExcepthookIntegration
	from sentry_sdk.integrations.modules import ModulesIntegration

	from frappe.utils.sentry import FrappeIntegration, before_send

	integrations = [
		AtexitIntegration(),
		ExcepthookIntegration(),
		DedupeIntegration(),
		ModulesIntegration(),
		ArgvIntegration(),
	]

	experiments = {}
	kwargs = {}

	if os.getenv("ENABLE_SENTRY_DB_MONITORING"):
		integrations.append(FrappeIntegration())
		experiments["record_sql_params"] = True

	if tracing_sample_rate := os.getenv("SENTRY_TRACING_SAMPLE_RATE"):
		kwargs["traces_sample_rate"] = float(tracing_sample_rate)

	if profiling_sample_rate := os.getenv("SENTRY_PROFILING_SAMPLE_RATE"):
		kwargs["profiles_sample_rate"] = float(profiling_sample_rate)

	sentry_sdk.init(
		dsn=sentry_dsn,
		before_send=before_send,
		attach_stacktrace=True,
		release=frappe.__version__,
		auto_enabling_integrations=False,
		default_integrations=False,
		integrations=integrations,
		_experiments=experiments,
		**kwargs,
	)
