from sys import stderr
from pickle import loads as pickle_loads
import frappe

from gevent.pool import Pool as GeventPool
from uuid import uuid4
from .client import RadishClient

def errprint(*args, **kwargs):
	print(*args, file=stderr, **kwargs)

class __AkkaRunner__(object):
	__slots__ = ['worker', 'radish_client', 'queue_name', 'akka_key']

	def __init__(self, worker, radish_client, queue_name, akka_key):
		self.worker = worker
		self.radish_client = radish_client
		self.queue_name = queue_name
		self.akka_key = akka_key

	def handle(self):
		THREAD_ID = str(uuid4())
		redis_conn = self.radish_client.conn
		worker = self.worker
		while True:
			next_task = redis_conn.get_next_job([THREAD_ID, self.akka_key])
			if not next_task:
				return

			try:
				unique_job_meta = redis_conn.job_meta_getter([next_task])
				if unique_job_meta:
					job_meta = pickle_loads(unique_job_meta)
				else:
					continue

				worker.handler.handle(worker.handler(**job_meta))

			except Exception as e:
				if worker.error_handler:
					worker.error_handler(e=e, queue_name=str(self.queue_name, 'utf-8'))
				else:
					raise
			finally:
				if resp := redis_conn.should_terminate([self.akka_key, THREAD_ID]):
					return


class Worker(object):
	def __init__(self, redis_queue_host, handler, error_handler, pool_size=50):
		self.__stopped = False
		self.__finished = False
		self.handler = handler
		self.error_handler = error_handler
		errprint('Connecting to', redis_queue_host)
		self.client = RadishClient(redis_url=redis_queue_host)
		self.client.conn.ping()
		errprint('Connected')
		handler.pool = self.pool = GeventPool(pool_size)

	def finish(self):
		self.__stopped = True
		while True:
			if not self.__finished:
				import gevent
				gevent.sleep(1)
			else:
				return

	def fetch_iterator(self, queues):
		conn = self.client.conn
		script_runner = self.client.conn.job_meta_getter
		rq_queues = [f'latte:squeue:{queue}' for queue in queues]

		while True:
			if self.__stopped:
				return

			fetched_value = conn.execute_command(
				'BZPOPMIN',
				*rq_queues,
				10,
			)

			if fetched_value is None:
				if self.__stopped:
					return
				continue
			elif self.__stopped:
				queue_name, job_name, score = fetched_value
				conn.execute_command(
					'ZADD',
					queue_name,
					score,
					job_name,
				)
				return

			queue_name, job_name, _ = fetched_value

			# job_meta = zlib.decompress(job_dict.data)
			job_name = str(job_name, 'utf-8')
			queue_name = str(queue_name, 'utf-8')

			if job_name.startswith('latte:akka:'):
				yield __AkkaRunner__(
					worker=self,
					radish_client=self.client,
					queue_name=queue_name,
					akka_key=job_name,
				)
				continue

			try:
				unique_job_meta = script_runner([job_name])
				if unique_job_meta:
					job_meta = pickle_loads(unique_job_meta)
				else:
					continue

				yield self.handler(**job_meta)

			except Exception as e:
				if self.error_handler:
					self.error_handler(e=e, queue_name=queue_name)
				else:
					raise

	def start(self, queues):
		for task in self.fetch_iterator(queues):
			self.pool.spawn(task.handle)
		self.__finished = True

