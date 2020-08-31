from __future__ import unicode_literals, print_function
import redis
from frappe.utils import cstr
from collections import defaultdict
import frappe
import os, socket
from frappe import _
from six import string_types
from types import FunctionType, MethodType
from pickle import dumps as pickle_dumps, loads as pickle_loads
from gevent.pool import Pool as GeventPool
from uuid import uuid4
from time import perf_counter
import frappe.monitor
from frappe import _dict
from gevent import Timeout
from frappe import local

# imports - third-party imports

default_timeout = 300
queue_timeout = {
	'background': 2500,
	'long': 1500,
	'default': 300,
	'short': 300
}

redis_connection = None

def enqueue(method, queue='default', timeout=None, event=None, set_user=None,
	method_name=None, job_name=None, now=False, enqueue_after_commit=False, **kwargs):
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

	if timeout is None:
		timeout = queue_timeout.get(timeout, default_timeout)

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
		"site": local.site,
		"timeout": timeout,
		"user": set_user or frappe.session.user,
		"method": method,
		"method_name": method_name,
		"event": event,
		"job_name": job_name or cstr(method),
		"job_run_id": create_job_run_log(method_name),
		"kwargs": kwargs,
		"queue": queue,
	}

	if enqueue_after_commit:
		local.db.run_after_commit(enqueue_to_redis, queue_args)
	else:
		enqueue_to_redis(queue_args)

SETTING_CACHE = {}
def bg_logging_enabled():
	try:
		timer, value = SETTING_CACHE[local.site]
		if perf_counter() - timer > 60:
			raise KeyError
		return value
	except KeyError:
		_, value = SETTING_CACHE[local.site] = (perf_counter(), local.db.get_single_value('System Settings', 'enable_bg_logger'),)
		return value

def create_job_run_log(method_name):
	if not bg_logging_enabled():
		return

	job_run = frappe.get_doc({
		'doctype': 'Job Run',
		'method': method_name,
		'status': 'Queued',
	})
	job_run.db_insert()
	return job_run.name

def enqueue_to_redis(kwargs):
	pickled = pickle_dumps(kwargs)
	# compressed = compress(pickled)
	conn = get_redis_conn()
	queue = kwargs["queue"]
	queue_name = f'frappe:bg:queue:{queue}'
	conn.lpush(queue_name, pickled)
	conn.incr(f'frappe:bg:counter:{queue}:total')

def enqueue_doc(doctype, name=None, method=None, queue='default', timeout=300,
	now=False, **kwargs):
	'''Enqueue a method to be run on a document'''
	return enqueue('frappe.utils.background_jobs.run_doc_method', doctype=doctype, name=name,
		doc_method=method, queue=queue, timeout=timeout, now=now, **kwargs)

def run_doc_method(doctype, name, doc_method, **kwargs):
	getattr(frappe.get_doc(doctype, name), doc_method)(**kwargs)

class Task(object):
	__slots__ = [
		'id', 'site', 'method', 'user', 'method_name', 'kwargs', 'queue',
		'timeout', 'flags', 'started_at', '_Task__job_run', 'job_run_id'
	]

	pool = GeventPool(50)

	@staticmethod
	def get_logger():
		try:
			return Task.__logger
		except AttributeError:
			Task.__logger = frappe.logger('bg_info')
			return Task.__logger

	def __init__(self, site, method, user, method_name, job_run_id, kwargs, queue, timeout, **flags):
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
		self.job_run_id = job_run_id
		self.kwargs = kwargs
		self.queue = queue
		self.timeout = timeout
		self.__job_run = None
		self.flags = _dict(flags)

	def process_task(self):
		return self.pool.spawn(fastrunner, self)

	def get_status(self):
		return 'queued'

	def log_start(self):
		if self.job_run_id:
			self.__job_run = frappe.get_doc('Job Run', self.job_run_id)
			self.started_at = self.__job_run.start()

	def success(self, end_time):
		if self.__job_run:
			self.__job_run.finish('Success')

	def failed(self, error_log):
		if self.__job_run:
			self.__job_run.finish('Failed', error_log.name)

	@staticmethod
	def set_pool_size(size):
		Task.pool = GeventPool(size)

def fastrunner(task, before_commit=None):
	frappe.init(site=task.site)
	frappe.flags.task_id = str(uuid4())
	frappe.flags.runner_type = f'fastrunner-{task.queue}'
	frappe.connect()
	local.lang = local.db.get_default('lang')
	if task.user:
		frappe.set_user(task.user)
	else:
		frappe.set_user('Administrator')

	conn = get_redis_conn()
	if task.timeout:
		Timeout(task.timeout).start()

	try:
		task.log_start()
		if isinstance(task.method, string_types):
			task.method = frappe.get_attr(task.method)
		task.method(**task.kwargs)
		if before_commit:
			before_commit(task)
		end_time = perf_counter()
		local.db.commit()
		task.success(end_time)
		conn.incr(f'frappe:bg:counter:{task.queue}:success')
	except Exception:
		local.db.rollback()
		traceback = frappe.get_traceback()
		print(traceback)
		error_log = frappe.log_error(title=task.method_name, message=traceback)
		task.failed(error_log)
		conn.incr(f'frappe:bg:counter:{task.queue}:failed')
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

	def add_to_dict(task):
		try:
			jobs_per_site[task.site].append(getattr(task, key))
		except AttributeError:
			if key in task.kwargs:
				# optional keyword arguments are stored in 'kwargs' of 'kwargs'
				jobs_per_site[task.site].append(task.kwargs[key])

	for queue in get_queue_list(queue):
		for task in get_task_list(queue):
			if site is None:
				add_to_dict(task)

			elif task.site == site:
				add_to_dict(task)

	return jobs_per_site

def get_task_list(queue):
	conn = get_redis_conn()
	return [Task(**pickle_loads(task_bin)) for task_bin in conn.lrange(f'frappe:bg:queue:{queue}', 0, -1)]

def get_queue_list(queue_list=None):
	'''Defines possible queues. Also wraps a given queue in a list after validating.'''
	default_queue_list = list(queue_timeout)
	if queue_list:
		if isinstance(queue_list, string_types):
			queue_list = [queue_list]

		return queue_list

	else:
		return default_queue_list

def validate_queue(queue, default_queue_list=None):
	if not default_queue_list:
		default_queue_list = list(queue_timeout)

	if queue not in default_queue_list:
		frappe.throw(_("Queue should be one of {0}").format(', '.join(default_queue_list)))

def get_redis_conn():
	if not hasattr(local, 'conf'):
		raise Exception('You need to call frappe.init')

	elif not local.conf.redis_queue:
		raise Exception('redis_queue missing in common_site_config.json')

	global redis_connection

	if not redis_connection:
		redis_connection = redis.from_url(local.conf.redis_queue, decode_responses=True)

	return redis_connection

def enqueue_test_job():
	enqueue('frappe.utils.background_jobs.test_job', s=100)

def test_job(s):
	import time
	print('sleeping...')
	time.sleep(s)
