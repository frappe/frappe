import frappe
from frappe.tests.classes.integration_test_case import IntegrationTestCase
from frappe.realtime import dispatch_realtime_event
from unittest.mock import patch
import requests

class TestRealtimeInMemory(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.original_in_memory = frappe.conf.get("in_memory")
		self.original_socketio_port = frappe.conf.get("socketio_port")

	def tearDown(self):
		if self.original_in_memory is not None:
			frappe.conf["in_memory"] = self.original_in_memory
		else:
			frappe.conf.pop("in_memory", None)
			
		if self.original_socketio_port is not None:
			frappe.conf["socketio_port"] = self.original_socketio_port
		else:
			frappe.conf.pop("socketio_port", None)
		super().tearDown()

	@patch("frappe.realtime.emit_via_redis")
	@patch("frappe.realtime.emit_via_webhook")
	def test_dispatcher_routing_redis(self, mock_webhook, mock_redis):
		frappe.conf["in_memory"] = 0
		dispatch_realtime_event("test_event", {"data": "test"}, "room")
		
		mock_redis.assert_called_once_with("test_event", {"data": "test"}, "room")
		mock_webhook.assert_not_called()

	@patch("frappe.realtime.emit_via_redis")
	@patch("frappe.realtime.emit_via_webhook")
	def test_dispatcher_routing_webhook(self, mock_webhook, mock_redis):
		frappe.conf["in_memory"] = 1
		dispatch_realtime_event("test_event", {"data": "test"}, "room")
		
		mock_webhook.assert_called_once_with("test_event", {"data": "test"}, "room")
		mock_redis.assert_not_called()

	@patch("requests.post")
	def test_webhook_payload_structure(self, mock_post):
		frappe.conf["in_memory"] = 1
		frappe.conf["socketio_port"] = 9999
		
		dispatch_realtime_event("test_event", {"data": "test"}, "test_room")
		
		mock_post.assert_called_once()
		args, kwargs = mock_post.call_args
		
		self.assertEqual(args[0], "http://localhost:9999/_internal/publish_event")
		self.assertEqual(kwargs.get("timeout"), 1)
		
		payload = kwargs.get("json")
		self.assertIsNotNone(payload)
		self.assertEqual(payload["event"], "test_event")
		self.assertEqual(payload["message"], {"data": "test"})
		self.assertEqual(payload["room"], "test_room")
		self.assertEqual(payload["namespace"], frappe.local.site)

	@patch("requests.post")
	def test_webhook_graceful_failure(self, mock_post):
		frappe.conf["in_memory"] = 1
		mock_post.side_effect = requests.exceptions.ConnectionError("Node server down")
		
		# Should not raise an exception
		try:
			dispatch_realtime_event("test_event", {"data": "test"}, "test_room")
		except Exception as e:
			self.fail(f"Webhook emit raised an exception when server was down: {e}")
