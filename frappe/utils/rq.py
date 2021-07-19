import redis

import frappe
from frappe.utils import get_site_id, get_bench_id, random_string


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
		d['enabled'] = True
		d['keys'] = cls.get_acl_key_rules()
		d['commands'] = cls.get_acl_command_rules()
		return d

	@classmethod
	def get_acl_key_rules(cls, include_key_prefix=False):
		"""FIXME: Find better way
		"""
		rules = ['rq:[^q]*', 'rq:queues', f'rq:queue:{get_bench_id()}:*']
		if include_key_prefix:
			return ['~'+pattern for pattern in rules]
		return rules

	@classmethod
	def get_acl_command_rules(cls):
		return ['+@all', '-@admin']

	@classmethod
	def gen_acl_list(cls, reset_passwords=False, set_admin_password=False):
		"""Generate list of ACL users needed for this branch.

		This list contains default ACL user and the bench ACL user(used by all sites incase of ACL is enabled).
		"""
		with frappe.init_site():
			bench_username = get_bench_id()
			bench_user_rules = cls.get_acl_key_rules(include_key_prefix=True) + cls.get_acl_command_rules()

		bench_user_rule_str = ' '.join(bench_user_rules).strip()
		bench_user_password = random_string(20)
		bench_user_resetpass = (reset_passwords and 'resetpass') or ''

		default_username = 'default'
		_default_user_password = random_string(20) if set_admin_password else ''
		default_user_password = '>'+_default_user_password if _default_user_password else 'nopass'
		default_user_resetpass = (reset_passwords and set_admin_password and 'resetpass') or ''

		return [
			f'user {default_username} on {default_user_password} {default_user_resetpass} ~* &* +@all',
			f'user {bench_username} on >{bench_user_password} {bench_user_resetpass} {bench_user_rule_str}'
		], {'bench': (bench_username, bench_user_password), 'default': (default_username, _default_user_password)}
