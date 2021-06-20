import redis

import frappe
from frappe.utils import get_site_id, get_bench_id


class RedisQueue:
	def __init__(self, conn):
		self.conn = conn

	def add_user(self, username, password=None):
		"""Create or update the user.
		"""
		password = password or self.conn.acl_genpass()
		user_settings = self.get_new_user_settings(username, password)
		is_created = self.conn.acl_setuser(**user_settings)
		return frappe._dict(user_settings) if is_created else {}

	@classmethod
	def get_connection(cls, username='default', password=None):
		domain = frappe.local.conf.redis_queue.split("redis://", 1)[-1]
		url = f"redis://{username}:{password or ''}@{domain}"
		conn = redis.from_url(url)
		conn.ping()
		return conn

	@classmethod
	def new(cls, username='default', password=None):
		return cls(cls.get_connection(username, password))

	@classmethod
	def set_admin_password(cls, cur_password=None, new_password=None, reset_passwords=False):
		username = 'default'
		conn = cls.get_connection(username, cur_password)
		password = '+'+(new_password or conn.acl_genpass())
		conn.acl_setuser(
			username=username, enabled=True, reset_passwords=reset_passwords, passwords=password
		)
		return password[1:]

	@classmethod
	def get_new_user_settings(cls, username, password):
		d = {}
		d['username'] = username
		d['passwords'] = '+'+password
		d['reset_keys'] = True
		d['reset_passwords'] = True
		d['enabled'] = True
		d['keys'] = cls.get_acl_key_rules()
		d['commands'] = cls.get_acl_command_rules()
		return d

	@classmethod
	def get_acl_key_rules(cls):
		"""FIXME: Find better way
		"""
		return ['rq:[^q]*', 'rq:queues', f'rq:queue:{get_bench_id()}:*']

	@classmethod
	def get_acl_command_rules(cls):
		return ['+@all', '-@admin']
