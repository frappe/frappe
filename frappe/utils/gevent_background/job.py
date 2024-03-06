import frappe
from frappe.model.document import Document
from frappe.app import _sites_path as SITES_PATH
from six import string_types
from types import FunctionType, MethodType
from functools import wraps
from uuid import uuid4
from pickle import dumps as pickle_dumps
from frappe.utils.python_perf import register_perfer, unregister_perfer
from time import perf_counter
from sys import stderr
from zlib import compress
from frappe import local
from datetime import datetime
from frappe.custom.doctype.background_job_config.background_job_config import BackgroundJobConfig
from frappe.utils import cint
from gevent import sleep
from collections.abc import Callable
from frappe.utils.gevent_background.radish import RadishClient
import base64

SUCCESS = 'Success'
FAILURE = 'Failure'
PROCESSING = 'Processing'
PENDING = 'Pending'
BACKPRESSURE_KEY = 'db_backpressure_count'
RETRIES_EXHAUSTED = 'Retries Exhausted'

def enqueue(
		method,
		queue='default',
		timeout=None,
		event=None,
		monitor=None,
		set_user=None,
		method_name=None,
		job_ident=None,
		job_name=None,
		now=False,
		enqueue_after_commit=False,
		sessionless=False,
		partition_key=None,
		on_kafka=False,
		parse_to_primitives=False,
		job_priority=1,
		akka_key=None,
		enqueue_after_commit_all=False,
		job_run_id=None,
		on_success: Callable = None,
		on_failure: Callable = None,
		at_front: bool = False,
		**kwargs
	):
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
	'''
		is_async is almost same as now need to implement
		at_front can be implemented by job_prioriy
		deduplicate already implemented
	'''

	kwargs.pop('async', None)
	kwargs.pop('is_async', None)

	if at_front:
		job_priority = 10

	if monitor is not False:
		monitor = monitor or frappe.local.conf.enable_global_monitor

	if now or local.flags.in_migrate or local.flags.in_install_app or local.flags.in_install or local.flags.run_jobs_realtime:
		if isinstance(method, str):
			method = frappe.get_attr(method)
		return method(**kwargs)

	if not method_name:
		if type(method) in (FunctionType, MethodType):
			method_name = f'{method.__module__}.{method.__qualname__}'
		else:
			method_name = str(method)

	retriable = False
	if admin_config := get_job_configs().get(method_name):
		if admin_config.job_disabled:
			return

		queue = admin_config.queue or queue
		job_priority = admin_config.priority or job_priority
		on_kafka = admin_config.on_kafka
		monitor = admin_config.monitor
		if not on_kafka:
			partition_key = None

		retriable = not not admin_config.max_retries

	retry_params = {}
	if retriable:
		retry_params = kwargs.copy()
		retry_params['queue'] 	= queue
		retry_params['timeout'] = timeout
		retry_params['event'] 	= event
		retry_params['monitor'] = monitor
		retry_params['set_user']= set_user
		retry_params['method_name'] = method_name
		retry_params['job_ident'] 	= job_ident
		retry_params['job_name'] 	= job_name
		retry_params['now'] = now
		retry_params['enqueue_after_commit'] = enqueue_after_commit
		retry_params['sessionless'] = sessionless
		retry_params['partition_key'] = partition_key
		retry_params['on_kafka'] = on_kafka
		retry_params['parse_to_primitives'] = parse_to_primitives
		retry_params['job_priority'] = job_priority
		retry_params['akka_key'] = akka_key
		retry_params['enqueue_after_commit_all'] = enqueue_after_commit_all
		retry_params['job_run_id'] = job_run_id

	# job_run_id = monitor and (job_run_id or create_job_run(method, queue, ident=job_ident, params=retry_params, retriable=retriable).name)

	if not queue:
		queue = 'default'

	if job_name:
		job_name = f'{method_name}:{job_name}'

	if akka_key:
		akka_key = f'latte:akka:{akka_key}'

	docs = []
	method_meta = None

	if parse_to_primitives:
		for key, value in kwargs.items():
			if isinstance(value, Document):
				docs.append((key, value.doctype, value.name,))
				kwargs[key] = None

		if type(method) == MethodType and isinstance(method.__self__, Document):
			method_meta = [
				method.__self__.doctype,
				method.__self__.name,
				method.__name__,
			]
			method = None

	queue_args = {
		"docs": docs,
		"event": event,
		"job_name": job_name or str(uuid4()),
		"job_run_id": job_run_id,
		"kwargs": kwargs,
		"log_flags": {},
		"method": method,
		"method_meta": method_meta,
		"method_name": method_name,
		"partition_key": partition_key,
		"priority": job_priority,
		"queue": queue,
		"request_id": local.flags.request_id,
		"sessionless": sessionless,
		"site": local.site,
		"timeout": timeout,
		"user": set_user or frappe.session.user,
		"on_kafka": on_kafka,
		"akka_key": akka_key,
		"monitor": monitor,
		"job_ident": job_ident,
		"retry_params": retry_params,
		"retriable": retriable,
		'on_success': on_success,
		'on_failure': on_failure
	}

	def enqueue_call():
		enqueue_to_queue(queue_args)

	if enqueue_after_commit or enqueue_after_commit_all:
		frappe.db.after_commit.add(enqueue_call)
		return
	else:
		enqueue_to_queue(queue_args)


def get_job_configs():
	all_jobs = frappe.get_all('Background Job Config', fields=[
		'job_name', 'queue', 'priority', 'job_disabled', 'on_kafka',
		'monitor', 'max_retries', 'retry_intervals',
	])
	for row in all_jobs:
		if row.retry_intervals:
			try:
				row.retry_intervals = [int(var.strip()) for var in row.retry_intervals.split(',') if var.strip()]
			except:
				row.retry_intervals = None

		row.retry_intervals = row.retry_intervals or [1,1,2,3,5,8]

	return {
		row.job_name: row
		for row in all_jobs
	}
radish_client = RadishClient(loader=lambda: (local.conf.redis_queues if 'redis_queues' in local.conf else local.conf.redis_queue))

def enqueue_to_queue(queue_args):
	# Creating job run id if monitor is enabled and job_run_id is not passed.
	queue_args['job_run_id'] = queue_args['monitor'] and (queue_args['job_run_id'] or \
			   create_job_run(
					queue_args['method'],
					queue_args['queue'],
					ident=queue_args['job_ident'],
					params=queue_args['retry_params'],
					retriable=queue_args['retriable']
					).name)

	queue_args["log_flags"]["enqueued_at"] = datetime.utcnow()

	set_loader(radish_client,queue_args['job_name'],pool=set_pool(str(queue_args['method_name'])),key=queue_args['akka_key'])
	response = radish_client.enqueue(queue_args)
	if queue_args['job_run_id'] and not response and not local.conf.disable_redis_hsetnx:
		mark_job_as_duplicate(queue_args['job_run_id'])

def mark_job_as_duplicate(job_run_id):
	job_run_doc = frappe.get_doc('Job Run', job_run_id)
	job_run_doc.update_status('Duplicate')


def create_job_run(method, queue=None, ident=None, params=None, retriable=False):
	if type(method) in (FunctionType, MethodType):
		method = f'{method.__module__}.{method.__qualname__}'
	else:
		method = str(method)

	doc = frappe.get_doc({
		'doctype': 'Job Run',
		'method': method,
		'ident': ident,
		'title': method,
		'status': PENDING,
		'enqueued_at': frappe.utils.now_datetime(),
		'queue_name': queue,
		'retry_count': 0,
		'retriable': int(retriable),
		'params' : str(base64.b64encode(pickle_dumps(params)),'utf-8') if retriable else '',
	})
	doc.db_insert()
	return doc

def background(identity=None, enqueue_after_commit=True, partition_key=None, parse_to_primitives=False, **dec_args):
	def decorator(fn):
		@wraps(fn)
		def decorated(*pos_args, __run__now=False, __pos__args=[], __primitive_pos_args={}, **kw_args):
			if __run__now:
				if parse_to_primitives:
					for idx, (dt, dn) in __primitive_pos_args.items():
						__pos__args[idx] = frappe.get_doc(dt, dn)

				fn(*__pos__args, **kw_args)
			else:
				calc_partition_key = partition_key(*pos_args, **kw_args) if callable(partition_key) else partition_key
				kw_args.update(dec_args)
				job_ident = identity and identity(*pos_args, **kw_args)
				if parse_to_primitives:
					pos_args = list(pos_args)
					for idx in range(len(pos_args)):
						if isinstance((value := pos_args[idx]), Document):
							__primitive_pos_args[idx] = (value.doctype, value.name,)
							pos_args[idx] = None

				return enqueue(
					decorated,
					__run__now=True,
					__pos__args=pos_args,
					__primitive_pos_args=__primitive_pos_args,
					job_ident=job_ident,
					# monitor=True,
					partition_key=calc_partition_key,
					parse_to_primitives=parse_to_primitives,
					enqueue_after_commit=enqueue_after_commit,
					**kw_args,
				)
		return decorated
	return decorator

class Task(object):
	__slots__ = ['id', 'site', 'method', 'user', 'method_name', 'job_name', 'kwargs', 'queue',
				'request_id', 'job_run_id', 'sessionless', 'log_flags', 'flags', 'docs', 'pool','on_success','on_failure']

	class DontCatchMe(Exception):
		pass

	def __init__(self, site, method, user, queue, request_id=None, job_run_id=None, job_name=None, kwargs={},
		method_name='', sessionless=False, log_flags={}, docs=[],on_success:Callable = None, on_failure: Callable = None,**flags):
		self.id = str(uuid4())
		self.site = site
		self.method = method
		self.user = user

		if not method_name:
			if isinstance(method, string_types):
				method_name = method
			else:
				method_name = f'{self.method.__module__}.{self.method.__qualname__}'

		self.method_name = method_name
		self.kwargs = kwargs
		self.queue = queue
		self.request_id = request_id
		self.job_name = job_name
		self.job_run_id = job_run_id
		self.sessionless = sessionless
		self.flags = _dict(flags)
		self.log_flags = log_flags
		self.docs = docs
		self.flags['start_time'] = datetime.now()
		self.on_success = on_success
		self.on_failure = on_failure

	def handle(task, before_commit=None):
		perfer = register_perfer()
		task.log_flags['started_at'] = datetime.utcnow()
		frappe.init(site=task.site, sites_path=SITES_PATH)
		set_loader(radish_client,task.job_name,pool=set_pool(str(task.method_name)),key=task.flags.akka_key)
		conn = radish_client.conn
		db_backpressure_limit = local.conf.get('db_backpressure_limit', 0)
		# latte.local.flags.sessionless = task.sessionless
		local.flags.request_id = task.request_id
		local.flags.task_id = str(uuid4())
		local.flags.runner_type = f'fastrunner-{task.queue}'

		if db_backpressure_limit:
			wait_for_clearance(conn, BACKPRESSURE_KEY, db_backpressure_limit)

		local.flags.current_running_method = task.method_name

		try:
			RadishClient.get_redis_bg_conn().hincrby(f'latte:current_run-{task.queue}', task.method_name, 1)
			frappe.connect(set_admin_as_user=False)
			local.lang = frappe.db.get_default('lang')
			if task.user:
				frappe.set_user(task.user)
			else:
				frappe.set_user('Administrator')

			if job_run_doc := (task.job_run_id and frappe.get_doc('Job Run', task.job_run_id)):
				job_run_doc.update_status(PROCESSING)

			if task.method is None and (meta := task.flags.get('method_meta')):
				task.method = getattr(frappe.get_doc(meta[0], meta[1]), meta[2])

			if isinstance(task.method, string_types):
				task.method = frappe.get_attr(task.method)

			for key, dt, dn in task.docs:
				task.kwargs[key] = frappe.get_doc(dt, dn)

			task.method(**task.kwargs)
			if before_commit:
				before_commit(task)

			if job_run_doc:
				job_run_doc.update_status(SUCCESS)
			if task.on_success:
				task.on_success()
			frappe.db.commit()
		except Exception as e:
			traceback = frappe.get_traceback()
			frappe.db.rollback()
			error_log = frappe.log_error(title=task.method_name, message=traceback)

			if job_run_doc := (task.job_run_id and frappe.get_doc('Job Run', task.job_run_id)):
				job_run_doc.error_log = error_log.name
				job_run_doc.update_status(FAILURE)
				frappe.db.commit()
			if task.on_failure:
				task.on_failure()
			print(traceback, file=stderr)

			if isinstance(e, Task.DontCatchMe):
				raise

		finally:
			unregister_perfer(perfer)
			try:
				RadishClient.get_redis_bg_conn().hincrby(f'latte:current_run-{task.queue}', task.method_name, -1, pool_key='bg_monitor')
			except:
				pass

			frappe.destroy()
			if db_backpressure_limit:
				conn.decr(BACKPRESSURE_KEY)

def wait_for_clearance(conn, key, limit):
	currently_running = conn.incr(key)
	if currently_running > limit:
		while (currently_running := cint(conn.get(key))) > limit:
			print('Waiting for sql, current_txns =', currently_running)
			sleep(1)

@frappe.whitelist()
def get_queue_depth():
	count_dict = {}
	if 'redis_queues' in local.conf:
		for queue in local.conf.redis_queues:
			radish_client.loader = lambda: queue
			queue_depth = radish_client.get_queue_depth().items()
			for queue_type, message in queue_depth:
				if queue_type in count_dict:
					count_dict[queue_type] += message
				else:
					count_dict[queue_type] = message
	else:
		queue_depth = radish_client.get_queue_depth().items()
		for queue_type, message in queue_depth:
			if queue_type in count_dict:
				count_dict[queue_type] += message
			else:
				count_dict[queue_type] = message
	return count_dict
@frappe.whitelist()
def get_current_running_functions_count(queue):
	return radish_client.get_current_running_functions_count(queue)

def flush_akka_keys():
	if 'redis_queues' in local.conf:
		for queue in local.conf.redis_queues:
			radish_client.loader = lambda: queue
			for key in radish_client.get_akka_keys():
				print(key)
				enqueue(
					frappe.ping,
					akka_key=key,
				)
	else:
		for key in radish_client.get_akka_keys():
			print(key)
			enqueue(
				frappe.ping,
				akka_key=key,
			)
def set_loader(radish_client,job_name,pool,key=None):
	if 'redis_queues' in local.conf:
		if key:
			radish_client.loader = lambda: pool[abs(hash(str(key)))  % len(pool)]
		else:
			radish_client.loader = lambda: pool[abs(hash(str(job_name)))  % len(pool)]

def set_pool(key):
	if local.conf.use_named_queue_pool:
		queue_pools = local.conf.named_queue_pool.pools
		queue_methods = local.conf.named_queue_pool.methods
		return queue_pools[queue_methods.get(key,'default')]
	else:
		if 'redis_queues' in local.conf:
			return local.conf.redis_queues
		return local.conf.redis_queue

class _dict(dict):
	"""dict like object that exposes keys as attributes"""
	def __getattr__(self, key):
		ret = self.get(key)
		if not ret and key.startswith("__"):
			raise AttributeError()
		return ret
	def __setattr__(self, key, value):
		self[key] = value
	def __getstate__(self):
		return self
	def __setstate__(self, d):
		self.update(d)
	def update(self, d):
		"""update and return self -- the missing dict feature in python"""
		super(_dict, self).update(d)
		return self
	def copy(self):
		return _dict(dict(self).copy())

dict = dict