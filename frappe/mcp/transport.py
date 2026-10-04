"""Buffer one SDK ASGI response inside the authenticated WSGI request."""

from urllib.parse import urlsplit

import anyio
from mcp.server.transport_security import TransportSecuritySettings
from werkzeug.wrappers import Response

import frappe
from frappe.mcp.server import create_server
from frappe.utils import get_url


async def serve(request):
	server = create_server()
	url = urlsplit(get_url(allow_header_override=False))
	origins = frappe.conf.allow_cors or []
	if isinstance(origins, str):
		origins = [origins]
	# A wildcard CORS setting must not disable the SDK's Origin check.
	security = TransportSecuritySettings(
		allowed_hosts=[url.netloc],
		allowed_origins=[f"{url.scheme}://{url.netloc}", *[origin for origin in origins if origin != "*"]],
	)
	app = server.streamable_http_app(
		streamable_http_path="/api/mcp",
		stateless_http=True,
		json_response=True,
		transport_security=security,
		max_request_body_size=request.max_content_length or 25 * 1024 * 1024,
	)
	bridge = HTTPBridge(request)
	# Each request has its own manager. No session or async task survives WSGI cleanup.
	async with server.session_manager.run():
		await app(bridge.scope, bridge.receive, bridge.send)
	return Response(bytes(bridge.body), status=bridge.status, headers=bridge.headers)


class HTTPBridge:
	def __init__(self, request):
		self.request = request
		self.received = False
		self.body = bytearray()
		self.status = 500
		self.headers = []
		self.scope = {
			"type": "http",
			"asgi": {"version": "3.0", "spec_version": "2.3"},
			"http_version": "1.1",
			"method": request.method,
			"scheme": request.scheme,
			"path": "/api/mcp",
			"raw_path": b"/api/mcp",
			"root_path": "",
			"query_string": request.query_string,
			"headers": [
				(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in request.headers
			],
			"server": (urlsplit(request.url).hostname, int(request.environ.get("SERVER_PORT", 80))),
			"client": (request.remote_addr or "", 0),
		}

	async def receive(self):
		if self.received:
			await anyio.sleep_forever()
		self.received = True
		return {"type": "http.request", "body": self.request.get_data(), "more_body": False}

	async def send(self, message):
		if message["type"] == "http.response.start":
			self.status = message["status"]
			self.headers = [
				(key.decode("latin-1"), value.decode("latin-1")) for key, value in message["headers"]
			]
		elif message["type"] == "http.response.body":
			self.body.extend(message.get("body", b""))
