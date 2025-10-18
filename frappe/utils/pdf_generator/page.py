import base64
import time
import urllib

import frappe

"""
CDP commands documentation can be found here.
https://chromedevtools.github.io/devtools-protocol/
"""


class Page:
	def __init__(self, session, browser_context_id, page_type):
		self.session = session
		result, error = self.session.send(
			"Target.createTarget", {"url": "", "browserContextId": browser_context_id}
		)
		if error:
			frappe.log_error(title="Error creating new page:", message=f"{error}")

		self.target_id = result["targetId"]
		self.type = page_type
		result, error = self.session.send(
			"Target.attachToTarget", {"targetId": self.target_id, "flatten": True}
		)
		if error:
			raise RuntimeError(f"Error attaching to target: {error}")
		self.session_id = result["sessionId"]
		self.send("Page.enable")
		self.frame_id = None
		self.get_frame_id_on_demand()
		self.set_media_emulation("print")
		self.set_cookies()

	# TODO: make send to return future and don't wait for it by default.
	def send(self, method, params=None, return_future=False):
		if params is None:
			params = {}
		return self.session.send(method, params, self.session_id, return_future)

	def get_frame_id_on_demand(self):
		if self.frame_id:
			return self.frame_id
		try:
			result, error = self.send("Page.getFrameTree")
			if error:
				raise RuntimeError(f"Error fetching frameId: {error}")
			frame_tree = result["frameTree"]
			frame = frame_tree["frame"]
			self.frame_id = frame["id"]
			return self.frame_id
		except Exception:
			frappe.log_error(title="Error fetching frameId:", message=f"{frappe.get_traceback()}")
			raise

	def _ensure_frame_id(self):
		if not self.frame_id:
			self.get_frame_id_on_demand()
		return self.frame_id

	def set_media_emulation(self, media_type: str = "print"):
		"""Set media emulation for the page."""
		return self.send("Emulation.setEmulatedMedia", {"media": media_type})

	def set_cookies(self):
		if frappe.session and frappe.session.sid and hasattr(frappe.local, "request"):
			domain = frappe.utils.get_host_name().split(":", 1)[0]
			cookie = {
				"name": "sid",
				"value": frappe.session.sid,
				"domain": domain,
				"sameSite": "Strict",
			}
			_result, error = self.send("Network.enable")
			if error:
				raise RuntimeError(f"Error enabling network: {error}")
			_result, error = self.send("Network.setCookie", cookie)
			if error:
				raise RuntimeError(f"Error setting cookie: {error}")
			_result, error = self.send("Network.disable")
			if error:
				raise RuntimeError(f"Error disabling network: {error}")

	def intercept_request_and_fulfill(self, url_pattern):
		"""Starts intercepting network requests for the given target_id and URL pattern."""
		data = {}

		def on_request_paused_event(future, response):
			"""Callback for when a request is paused (intercepted)."""
			params = response.get("params")
			if params and params.get("requestId"):
				data["request_id"] = params["requestId"]
				if not future.done():
					future.set_result(data["request_id"])

		# Start listening for requestPaused event
		event = self.session.start_listener(
			"Fetch.requestPaused", on_request_paused_event, self.session_id, self.target_id, self.frame_id
		)

		# Enable request interception for the specified URL pattern
		self.session.send("Fetch.enable", {"patterns": [{"urlPattern": url_pattern}]})

		def intercept_and_fulfill():
			self.session.wait_for_event(event)
			self.session.send(
				"Fetch.fulfillRequest",
				{"requestId": event[1].result(), "responseCode": 200},
				return_future=True,
			)
			self.session.remove_listener("Fetch.requestPaused", event)

		return intercept_and_fulfill

	def intercept_request_for_local_resources(self, url_pattern="*"):
		"""Starts intercepting network requests for the given target_id and URL pattern."""
		data = {}

		def on_request_paused_event(future, response):
			"""Callback for when a request is paused (intercepted)."""
			params = response.get("params")
			if params and params.get("requestId"):
				data["request_id"] = params["requestId"]
				url = params["request"]["url"]

				if url.startswith(frappe.request.host_url):
					path = url.replace(frappe.request.host_url, "").split("?v", 1)[0]
					if path.startswith("assets/") or path.startswith("files/"):
						path = urllib.parse.unquote(path)
						if path.startswith("files/"):
							path = frappe.utils.get_site_path("public", path)
						content = frappe.read_file(path, as_base64=True)
						response_headers = []
						# write logic to handle all file types as required
						if path.endswith(".svg"):
							response_headers.append({"name": "Content-Type", "value": "image/svg+xml"})
						if content:
							self.session.send(
								"Fetch.fulfillRequest",
								{
									"requestId": data["request_id"],
									"responseCode": 200,  # actually hande the response code from the request
									"responseHeaders": response_headers,
									"body": content,
								},
								return_future=True,
							)
							return
				self.session.send(
					"Fetch.continueRequest",
					{"requestId": data["request_id"]},
					return_future=True,
				)

		# Start listening for requestPaused event
		self.session.start_listener(
			"Fetch.requestPaused", on_request_paused_event, self.session_id, self.target_id, self.frame_id
		)

		# Enable request interception for the specified URL pattern
		self.session.send("Fetch.enable", {"patterns": [{"urlPattern": url_pattern}]})

	def set_tab_url(self, url):
		"""Navigate to a URL and fulfill the request with status code 200."""

		# Intercept and fulfill request with 200 status code
		wait_and_fulfill = self.intercept_request_and_fulfill(url)
		# Now, navigate after intercepting the request
		wait_start = self.wait_for_load(wait_for="load")
		page_navigate = self.send("Page.navigate", {"url": url}, return_future=True)
		wait_and_fulfill()

		def wait_for_navigate():
			self.session.wait_for_event(page_navigate, 3)
			wait_start()

		self.wait_for_navigate = wait_for_navigate

	def evaluate(self, expression, await_promise=False):
		self.send("Runtime.enable")
		result, error = self.send(
			"Runtime.evaluate", {"expression": expression, "awaitPromise": await_promise}
		)
		if error:
			# retry if error in 500ms for 3 times (just safe guard as i had few edge cases where it failed).
			# waiting for network is still slower than this.
			for _i in range(3):
				print(f"Error evaluating expression: {error}. Retrying in 500ms")
				time.sleep(0.5)
				result, error = self.send(
					"Runtime.evaluate", {"expression": expression, "awaitPromise": await_promise}
				)
				if not error:
					break
			raise RuntimeError(f"Error evaluating expression: {error}")

		self.send("Runtime.disable")
		return result

	# set wait_for to networkIdle if pdf is not rendering correctly.
	# if you face header Height to be incorrect as some external script is changing elements.
	# networkIdle is most stable option but make it a lot slower so avoiding for now. enable if not stable
	def set_content(self, html, wait_for=None):
		if not wait_for:
			wait_for = ["load", "DOMContentLoaded"]
		self.intercept_request_for_local_resources()
		wait_start = self.wait_for_load(wait_for=wait_for)
		self.send("Page.setDocumentContent", {"frameId": self._ensure_frame_id(), "html": html})
		self.wait_for_set_content = wait_start

	def wait_for_load(self, wait_for, timeout=60):
		self.send("Page.setLifecycleEventsEnabled", {"enabled": True})
		status = {}
		if isinstance(wait_for, str):
			status[wait_for] = False
		if isinstance(wait_for, list):
			for event in wait_for:
				status[event] = False

		def on_lifecycle_event(future, response):
			params = response.get("params", {})
			if params.get("name") in status.keys():
				status[params.get("name")] = True
				if all(status.values()):
					if not future.done():
						future.set_result(response)

		event = self.session.start_listener(
			"Page.lifecycleEvent", on_lifecycle_event, self.session_id, self.target_id, self.frame_id
		)

		def start_wait():
			self.session.wait_for_event(event, timeout)
			self.session.remove_listener("Page.lifecycleEvent", event)

		return start_wait

	def get_element_height(self, selector="body"):
		try:
			if not self.is_print_designer:
				selector = ".wrapper"
			self.send("DOM.enable")
			doc_result, doc_error = self.send("DOM.getDocument")
			if doc_error:
				raise RuntimeError(f"Error getting document node: {doc_error}")
			doc_node_id = doc_result["root"]["nodeId"]
			result, error = self.send("DOM.querySelector", {"nodeId": doc_node_id, "selector": selector})
			if error:
				raise RuntimeError(f"Error querying selector: {error}")
			node_id = result["nodeId"]
			result, error = self.send("DOM.getBoxModel", {"nodeId": node_id})
			if error:
				raise RuntimeError(f"Error getting computed style: {error}")
			height = result["model"]["height"]
		finally:
			self.send("DOM.disable")
		return height

	def add_page_size_css(self):
		width = str(self.options["paperWidth"]) + "in"
		height = str(self.options["paperHeight"]) + "in"
		marginLeft = str(self.options["marginLeft"]) + "in"
		marginRight = str(self.options["marginRight"]) + "in"
		marginTop = str(self.options["marginTop"]) + "in"
		marginBottom = str(self.options["marginBottom"]) + "in"

		# Enable DOM and CSS agents
		result, error = self.send("DOM.enable")
		if error:
			raise RuntimeError(f"Error enabling DOM: {error}")

		result, error = self.send("CSS.enable")
		if error:
			raise RuntimeError(f"Error enabling CSS: {error}")

		# Create a new stylesheet
		result, error = self.send("CSS.createStyleSheet", {"frameId": self._ensure_frame_id()})
		if error:
			raise RuntimeError(f"Error creating stylesheet: {error}")

		style_sheet_id = result["styleSheetId"]

		# Define the CSS rule for the page size
		css_rule = f"""
			@page {{
				size: {width} {height};
				margin: {marginTop} {marginRight} {marginBottom} {marginLeft};
			}}
		"""

		# Apply the CSS rule to the created stylesheet
		result, error = self.send("CSS.setStyleSheetText", {"styleSheetId": style_sheet_id, "text": css_rule})

		if error:
			raise RuntimeError(f"Error setting stylesheet text: {error}")

		self.send("CSS.disable")
		self.send("DOM.disable")

	def generate_pdf(self, wait_for_pdf=True, raw=False):
		self.add_page_size_css()
		if not wait_for_pdf:
			self.wait_for_pdf = self.send("Page.printToPDF", self.options, return_future=True)
			return

		result, error = self.send("Page.printToPDF", self.options)
		if error:
			raise RuntimeError(f"Error generating PDF: {error}")
		if "stream" not in result:
			raise ValueError("Stream handle not returned from Page.printToPDF")
		return self.get_pdf_from_stream(result["stream"], raw)

	def get_pdf_stream_id(self):
		# wait for task to complete
		self.session.wait_for_event(self.wait_for_pdf)
		# wait for event to complete
		task = self.wait_for_pdf.result()
		future = task.result()
		stream_id = future["result"]["stream"]
		return stream_id

	def get_pdf_from_stream(self, stream_id, raw=False):
		from io import BytesIO

		from pypdf import PdfReader

		pdf_data = b""
		offset = 0
		while True:
			chunk_result, error = self.send("IO.read", {"handle": stream_id, "offset": offset, "size": 4096})
			if error:
				raise RuntimeError(f"Error reading PDF chunk: {error}")
			chunk_data = chunk_result["data"]
			# we don't use base64Encode option but added check anyway as it is one of the valid options.
			if chunk_result.get("base64Encoded", False):
				chunk_data = base64.b64decode(chunk_data)
			pdf_data += chunk_data
			offset += len(chunk_data)
			if chunk_result.get("eof", False):
				break

		_result, error = self.send("IO.close", {"handle": stream_id})
		if error:
			raise RuntimeError(f"Error closing PDF stream: {error}")

		if raw:
			return pdf_data

		return PdfReader(BytesIO(pdf_data))

	def close(self):
		self.session.send("Fetch.disable")
		_result, error = self.send("Target.closeTarget", {"targetId": self.target_id})
		if error:
			raise RuntimeError(f"Error closing target: {error}")
