import redis
from pickle import dumps as pickle_dumps
from time import time_ns
import frappe

from frappe import local

OWNERS_KEY = 'AKKA_QUEUE_OWNERS'
TIMESTAMP_HASH = 'AKKA_QUEUE_LAST_TS'
QUEUE_UNIQUE_HASH = 'latte:queueuniquehash'
META_PREFIX = 'META_'
REDIS_BG_CONN = None
class RadishClient(object):
	CONNECTION_MAP = {}

	@classmethod
	def get_redis_conn(cls, redis_url):

		AKKA_KEY_EXPIRY = local.conf.akka_key_expiry or 600

		if redis_url in cls.CONNECTION_MAP:
			return cls.CONNECTION_MAP[redis_url]

		redis_connection = cls.CONNECTION_MAP[redis_url] = redis.from_url(redis_url)

		SET_COMMAND = 'hsetnx'
		if local.conf.disable_redis_hsetnx:
			SET_COMMAND = 'hset'

		# 1 - queue name
		# 2 - job_name
		# 3 - priority
		# 4 - pickled
		# 5 - Akka Key
		redis_connection.enqueue_job = redis_connection.register_script(f'''
			if KEYS[5] ~= '' then
				if not redis.call('GET', '{META_PREFIX}'..KEYS[5]) then
					redis.call('zadd', KEYS[1], KEYS[3], KEYS[5])
					redis.call('hdel', '{OWNERS_KEY}', KEYS[5])
					redis.call('SET', '{META_PREFIX}'..KEYS[5], 'ON')
				end
				redis.call('lpush', KEYS[5], KEYS[2])
			else
				redis.call('zadd', KEYS[1], KEYS[3], KEYS[2])
			end
			return redis.call('{SET_COMMAND}', "{QUEUE_UNIQUE_HASH}", KEYS[2], KEYS[4])
		''')

		# 1 Job Name
		redis_connection.job_meta_getter = redis_connection.register_script(f'''
			local pickled_data = redis.call('hget', '{QUEUE_UNIQUE_HASH}', KEYS[1])
			if pickled_data then
				redis.call('hdel', '{QUEUE_UNIQUE_HASH}', KEYS[1])
			end
			return pickled_data
		''')

		# 1 akka key
		# 2 worker uuid
		redis_connection.should_terminate = redis_connection.register_script(f'''
			local owner = redis.call('hget', '{OWNERS_KEY}', KEYS[1])
			if owner ~= KEYS[2] then
				return 2
			end
			if redis.call('llen', KEYS[1]) == 0 then
				redis.call('hdel', '{OWNERS_KEY}', KEYS[1])
				redis.call('hdel', '{TIMESTAMP_HASH}', KEYS[1])
				redis.call('DEL', '{META_PREFIX}'..KEYS[1])
				return 1
			end
		''')

		# 1 worker uuid
		# 2 akka key
		redis_connection.get_next_job = redis_connection.register_script(f'''
			local owner = redis.call('hget', '{OWNERS_KEY}', KEYS[2])
			if (not owner) then
				redis.call('hset', '{OWNERS_KEY}', KEYS[2], KEYS[1])
				owner = KEYS[1]
			end
			if owner == KEYS[1] then
				redis.call('hset', '{TIMESTAMP_HASH}', KEYS[2], redis.call('time')[1])
				redis.call('EXPIRE', '{META_PREFIX}'..KEYS[2], {AKKA_KEY_EXPIRY})
				return redis.call('rpop', KEYS[2])
			end
		''')

		return redis_connection

	def __init__(self, loader=None, redis_url=None):
		self.__redis_client = None
		self.loader = loader
		self.redis_url = redis_url

	@property
	def conn(self):
		if not self.__redis_client:
			self.__redis_client = self.get_redis_conn(self.redis_url or self.loader())

		return self.__redis_client

	def enqueue(self, queue_args):
		self.__redis_client = None
		conn = self.conn
		pickled = pickle_dumps(queue_args)
		job_name = queue_args['job_name']
		priority = queue_args['priority']
		job_score = int(time_ns() / (10 ** priority))
		# compressed = compress(pickled)
		queue_name = f'latte:squeue:{queue_args["queue"]}'
		response = conn.enqueue_job([
			queue_name,
			job_name,
			job_score,
			pickled,
			queue_args['akka_key'] or '',
		])
		return response

	@staticmethod
	def check_page_access_permission():
		user_roles = frappe.get_roles()
		permitted_roles = [each.role for each in frappe.get_doc("Page", "redis-monitor").roles]
		for permitted_role in permitted_roles:
			if(permitted_role in user_roles):
				return True
		return frappe.throw("You do not have the permission to view this page!")

	def get_queue_depth(self):
		self.check_page_access_permission()
		self.__redis_client = None
		conn = self.conn
		queues = conn.keys('latte:squeue:*')
		return {
			str(queue, 'utf-8').split('latte:squeue:')[1]: conn.zcount(queue, '0', 'inf')
			for queue in queues
		}

	def get_current_running_functions_count(self, queue):
		self.check_page_access_permission()
		return {
			str(k, 'utf-8'): str(v, 'utf-8')
			for k, v in self.get_redis_bg_conn().hgetall(f'latte:current_run-{queue}', pool_key='bg_monitor').items()
				if str(v, 'utf-8') != "0"
		}

	def reset_current_running_functions_counter(self, queue):
		self.check_page_access_permission()
		key = f'latte:current_run-{queue}'
		self.get_redis_bg_conn().hdelete(key)

	@staticmethod
	def get_redis_bg_conn():
		global REDIS_BG_CONN
		if not REDIS_BG_CONN:
			from frappe import cache
			REDIS_BG_CONN = cache
		return REDIS_BG_CONN

	def get_akka_keys(self):
		self.__redis_client = None
		for key in self.conn.scan_iter('latte:akka:*'):
			key = str(key, 'utf-8')
			yield key[11:]