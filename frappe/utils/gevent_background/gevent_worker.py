import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import gevent
import sys
import frappe

import signal
from sys import exit
from frappe.utils.gevent_background.job import Task

def start(queues=None):
	from gevent import spawn
	from frappe.utils.gevent_background.radish import Worker

	if not queues:
		queues = 'short,long,default'
	if isinstance(queues, str):
		queues = queues.split(',')
	frappe.init(site='')

	conf = frappe.local.conf
	redis_queues = conf.redis_queues if 'redis_queues' in conf else [conf.redis_queue]
	threads = []
	# Starting worker on seperate thread for each redis instance
	for redis_url in redis_queues:
		worker = Worker(
			redis_queue_host=redis_url,
			handler=Task,
			error_handler=handle_dequeue_error,
		)
		t = spawn(worker.start, queues=queues)
		gevent.signal_handler(signal.SIGHUP, graceful_shutdown, worker)
		gevent.signal_handler(signal.SIGINT, graceful_shutdown, worker)
		gevent.signal_handler(signal.SIGTERM, graceful_shutdown, worker)
		gevent.signal_handler(signal.SIGQUIT, graceful_shutdown, worker)
		threads.append(t)

	# Joining all threads to master thread
	HealthCheckProbe().start_server()

	gevent.joinall(threads)
	print("start done")
	GRACEFUL_SHUTDOWN_WAIT = 40 if not frappe.local.conf.GRACEFUL_SHUTDOWN_WAIT else frappe.local.conf.GRACEFUL_SHUTDOWN_WAIT
	graceful = Task.pool.join(timeout=GRACEFUL_SHUTDOWN_WAIT)
	print('Shutting down, Gracefully=', graceful)
	exit(0 if graceful else 1)


def handle_dequeue_error(e, queue_name):
	print(frappe.get_traceback(), file=sys.stderr)

def graceful_shutdown(worker, *args, **kwargs):
	print('Warm shutdown requested')
	worker.finish()


class SimpleServer(BaseHTTPRequestHandler):
	def do_GET(self):
		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()

class HealthCheckProbe:
	def __init__(self , host = "0.0.0.0" , port = int(os.environ.get('HEALTH_CHECK_PORT')) if os.environ.get('HEALTH_CHECK_PORT') else 8164):
		self.host = host
		self.port = port

	def web_worker(self):
		try:
			self.web_server = HTTPServer((self.host, self.port), SimpleServer)
			print("Server started http://%s:%s" % (self.host, self.port))
			self.web_server.serve_forever()
		except OSError:
			print(f"Port address {self.port} already in use")
		except KeyboardInterrupt:
			self.kill_server()

	def start_server(self):
		gevent.spawn(self.web_worker)

	def kill_server(self):
		self.web_server.server_close()
		print("Server stopped.")
