import functools
from collections.abc import Callable
from enum import StrEnum, auto

import frappe


class HealthState(StrEnum):
	healthy = auto()
	unhealthy = auto()


def health_check(func: Callable):
	"""
	Each health check is a function.
	- Successful return from function is considered as success.
	- Any uncaught exceptions are considered as failed health check.
	"""
	assert isinstance(func, Callable), "Invalid usage of decorator, Usage: @health_check"

	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		result = {"status": HealthState.healthy}
		try:
			func(*args, **kwargs)
		except Exception as e:
			result["status"] = HealthState.unhealthy
			result["error"] = str(e)
			print(frappe.get_traceback())

		return result

	return wrapper


class HealthChecker:
	def run_health_checks(self):
		response = {}
		status_code = 200

		response["redis"] = self.check_redis()
		response["db"] = self.check_db_reachable()
		response["rq"] = self.check_rq()

		for check in response.values():
			if check["status"] == HealthState.unhealthy:
				status_code = 500

		return response, status_code

	@health_check
	def check_redis(self):
		frappe.cache.ping()

	@health_check
	def check_rq(self):
		from frappe.utils.background_jobs import get_redis_conn

		get_redis_conn().ping()

	@health_check
	def check_db_reachable(self):
		from frappe.utils.connections import is_open

		config = frappe.conf
		db_type = config.get("db_type", "mariadb")

		if config.db_type == "sqlite":
			return

		db_host = config.get("db_host")
		db_port = config.get("db_port")
		if not (db_host and db_port):
			return

		assert is_open(db_type, db_host, db_port, None), "DB not reachable"

	@health_check
	def check_assets():
		# TODO
		pass
