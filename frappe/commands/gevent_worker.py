import frappe

import signal
import redis

from sys import exit
from frappe.utils.scheduler import enqueue_events_for_all_sites

GRACEFUL_SHUTDOWN_WAIT = 10

def start(queues=None, enable_scheduler=False):
	from gevent import spawn
	from gevent.signal import signal as handle_signal
	if not queues:
		queues = 'short,long,default'
	if isinstance(queues, str):
		queues = queues.split(',')
	frappe.init(site='')
	print(f'Starting Gevent worker for queues {queues}')
	handle_signal(signal.SIGHUP, graceful_shutdown)
	handle_signal(signal.SIGINT, graceful_shutdown)
	handle_signal(signal.SIGTERM, graceful_shutdown)
	if scheduler:
		spawn(scheduler)
	deque_and_enqueue(queues, frappe.local.conf)

def scheduler():
	from datetime import datetime
	from gevent import sleep, spawn
	sleep((60 - datetime.now().second) % 60)
	while True:
		print('Scheduler Tick')
		spawn(enqueue_events_for_all_sites)
		sleep(60)

def fetch_jobs_from_redis(queues, conf):
	from pickle import loads
	from frappe.utils.background_jobs import Task
	redis_queue_host = conf.get('redis_queue', 'redis://localhost:11000')
	log = frappe.logger('bg_info')
	conn = None
	print('Connecting to', redis_queue_host)
	conn = redis.StrictRedis.from_url(redis_queue_host)
	print('Connected')
	lpop = True
	rq_queues = [f'frappe:bg:queue:{queue}' for queue in queues]
	while True:
		lpop = not lpop
		queue_name, job_meta = conn.execute_command(
			'blpop' if lpop else 'brpop',
			*rq_queues,
			0,
		)
		# job_meta = zlib.decompress(job_dict.data)
		try:
			job_meta = loads(job_meta)
			yield Task(**job_meta)
		except Exception:
			log.info({
				'queue_name': queue_name,
				'method': '__NONE__',
				'pool_size': 0,
				'stage': 'Fatal',
				'traceback': frappe.get_traceback()
			})
			frappe.errprint(frappe.get_traceback())

def deque_and_enqueue(queues, conf):
	for task in fetch_jobs_from_redis(queues, conf):
		task.process_task()

def graceful_shutdown(*args, **kwargs):
	from frappe.utils.background_jobs import Task
	print('Warm shutdown requested')
	graceful = Task.pool.join(timeout=GRACEFUL_SHUTDOWN_WAIT)
	print('Shutting down, Gracefully=', graceful)
	exit(0 if graceful else 1)