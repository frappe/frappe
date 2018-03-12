"""
frappe.socketio
"""
import json
import logging

import six
import redis

import frappe

BROKER = None

log    = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class Broker(object):
	URL	    = 'redis://127.0.0.1:1200'
	CHANNEL = "socketio"

	def __init__(self):
		try:
			config      = frappe.get_conf()
			self.redis  = redis.Redis.from_url(
				config.redis_socketio if config else Broker.URL
			)
			self.pubsub = self.redis.pubsub()
			self.events = [ ]

			self.ok     = True
		except Exception as e:
			self.ok     = False
			self.error  = e

	def handle(self, message):
		print("Recieved event from Socket.IO with message: {message}".format(
			message = message
		))

		data  = json.loads(message['data'])
		names = [event['name'] for event in self.events]
		if 'event' in data and data['event'] in self.events:
			data = json.loads(data['data'])
	
	def raise_error(self, error):
		if self.error:
			raise self.error

	def get(cache = True):
		global BROKER
		if not BROKER or not cache:
			BROKER = Broker()
			BROKER.sub()
		return BROKER

	def pub(self, event, data):
		packet    = dict(
			event = event,
			data  = data
		)
		packet    = json.dumps(packet)

		self.redis.publish(Broker.CHANNEL, packet)

	def sub(self):
		if hasattr(self, 'thread') and self.thread:
			self.thread.stop()

		self.pubsub.subscribe(**{ Broker.CHANNEL: self.handle })
		# self.thread = self.pubsub.run_in_thread(sleep_time = 0.001)

	def register(self, event, handler):
		if event not in self.events:
			self.events.append({
				   'name': event,
				'handler': handler
			})
			self.pub("register", dict(name = event))

def on(event):
	"""
	@frappe.socketio.on("foo")
	def bar():
		return "baz"
	"""
	def decorator(function):
		broker = Broker.get()
		
		if broker.ok:
			broker.register(event, function)
		else:
			# Unable to connect, try again?
			broker.raise_error()

		return function

	return decorator

def emit(event, data):
	pass