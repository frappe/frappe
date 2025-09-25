import asyncio

import websockets

import frappe


class CDPSocketClient:
	"""
	Manages WebSocket communications with Chrome DevTools Protocol.
	Ensures robust error handling and consistent logging.
	"""

	def __init__(self, websocket_url):
		self.websocket_url = websocket_url
		self.connection = None
		self.message_id = 0
		self.pending_messages = {}
		self.listeners = {}
		self.listen_task = None
		self.loop = asyncio.new_event_loop()
		asyncio.set_event_loop(self.loop)

	def connect(self):
		"""Open the WebSocket connection and start listening for messages."""
		self.loop.run_until_complete(self._connect())
		self.listen_task = self.loop.create_task(self._listen())

	async def _connect(self):
		try:
			self.connection = await websockets.connect(self.websocket_url)
		except Exception:
			frappe.log_error(title="Failed to connect to WebSocket:", message=f"{frappe.get_traceback()}")
			raise

	async def _listen(self):
		try:
			async for message in self.connection:
				self._handle_message(frappe.json.loads(message))
		except Exception:
			frappe.log_error(title="WebSocket listening error:", message=f"{frappe.get_traceback()}")

	def _handle_message(self, response):
		method = response.get("method")
		params = response.get("params", {})
		session_id = response.get("sessionId")
		target_id = params.get("targetId")
		frame_id = params.get("frameId")
		message_id = response.get("id")

		composite_key = (method, session_id, target_id, frame_id)

		# Handle responses with `id`
		if message_id and message_id in self.pending_messages:
			future = self.pending_messages.pop(message_id)
			if composite_key in self.pending_messages:
				self.pending_messages.pop(composite_key)
			future.set_result(response)

		# Handle responses without `id` using a composite key
		elif method:
			if composite_key in self.pending_messages:
				# print("matched using composite_key", composite_key)
				future = self.pending_messages.pop(composite_key)
				future.set_result(response)

			if method in self.listeners:
				for callback, future, filters in self.listeners[method]:
					# added not filters["key"] might cause cross talk between different sessions
					if (
						(not session_id or not filters["sessionId"] or filters["sessionId"] == session_id)
						and (not target_id or not filters["targetId"] or filters["targetId"] == target_id)
						and (not frame_id or not filters["frameId"] or filters["frameId"] == frame_id)
					):
						callback(future, response)

	def disconnect(self):
		try:
			if self.listen_task:
				self.listen_task.cancel()
			self.loop.run_until_complete(self._disconnect())
			# Cancel all pending tasks before stopping the loop was causing degrading performance over time to not cancelled properly
			pending_tasks = [task for task in asyncio.all_tasks(self.loop) if not task.done()]
			for task in pending_tasks:
				task.cancel()
				try:
					self.loop.run_until_complete(task)  # Ensure tasks finish before loop stops
				except asyncio.CancelledError:
					pass  # Ignore cancellation errors
		except Exception:
			frappe.log_error(title="Error while disconnecting:", message=f"{frappe.get_traceback()}")
			raise

	async def _disconnect(self):
		try:
			if self.connection and not self.connection.closed:
				await self.connection.close()
			self.connection = None
		except Exception:
			frappe.log_error(
				title="Error during WebSocket disconnection:", message=f"{frappe.get_traceback()}"
			)

	def send(self, method, params=None, session_id=None, return_future=False):
		if return_future:
			return asyncio.ensure_future(
				self._send(method, params, session_id, wait_future_fulfill=False), loop=self.loop
			)
		future = self.loop.run_until_complete(self._send(method, params, session_id))
		return self._destructure_response(future.result())

	async def _send(self, method, params=None, session_id=None, wait_future_fulfill=True):
		self.message_id += 1
		message_id = self.message_id
		message = {
			"id": message_id,
			"method": method,
			"params": params or {},
		}

		if session_id:
			message["sessionId"] = session_id

		if self.connection is None:
			raise RuntimeError("WebSocket connection is not open.")

		future = asyncio.Future()
		self.pending_messages[message_id] = future

		# Dynamically create the composite key
		if any(
			[
				method,
				session_id,
				params.get("targetId") if params else None,
				params.get("frameId") if params else None,
			]
		):
			composite_key = (
				method,
				session_id,
				params.get("targetId") if params else None,
				params.get("frameId") if params else None,
			)
			self.pending_messages[composite_key] = future

		await self.connection.send(frappe.json.dumps(message))
		if wait_future_fulfill:
			await future
		return future

	def _destructure_response(self, response):
		"""Destructure the response to extract useful information."""
		result = response.get("result", None)
		error = response.get("error", None)
		return result, error

	def start_listener(self, method, callback, session_id=None, target_id=None, frame_id=None):
		"""Register a listener for a specific CDP event with optional filtering."""
		if method not in self.listeners:
			self.listeners[method] = []
		future = self.loop.create_future()

		event = (callback, future, {"sessionId": session_id, "targetId": target_id, "frameId": frame_id})
		if event not in self.listeners[method]:
			self.listeners[method].append(event)
		return event

	def wait_for_event(self, event, timeout=3):
		if type(event) is tuple:
			event = event[1]
		try:
			self.loop.run_until_complete(asyncio.wait_for(event, timeout))
		except asyncio.TimeoutError:
			frappe.log_error(title="Timeout waiting for event", message=f"{frappe.get_traceback()}")

	def remove_listener(self, method, event):
		"""Remove a listener for a specific CDP event."""
		self.listeners[method].remove(event)
