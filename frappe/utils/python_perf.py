from time import perf_counter
from frappe import throw
from gevent import getcurrent

ACTIVE_THREAD = {}

class PerferClass(object):
	__slots__ = [
		'python_time', 'last_active_timestamp', 'max_continuous_time',
		'total_switches', 'sql_running', 'sql_python_time'
	]
	def __init__(self):
		self.python_time = 0
		self.last_active_timestamp = perf_counter()
		self.max_continuous_time = 0
		self.total_switches = 0
		self.sql_running = False
		self.sql_python_time = 0

def register_perfer():
	perfer = ACTIVE_THREAD[getcurrent()] = PerferClass()
	return perfer

def unregister_perfer(perfer):
	execution_time = perf_counter() - perfer.last_active_timestamp
	if execution_time > perfer.max_continuous_time:
		perfer.max_continuous_time = execution_time

	perfer.python_time += execution_time
	thread = getcurrent()
	if thread in ACTIVE_THREAD:
		del ACTIVE_THREAD[getcurrent()]
