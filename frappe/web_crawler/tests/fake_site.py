import socket
from io import BytesIO
from unittest.mock import patch

from urllib3.response import HTTPResponse

import frappe
from frappe.tests.classes.context_managers import change_settings

PUBLIC_ADDRESS = "93.184.216.34"
HTML = "text/html; charset=utf-8"
NEUTRAL_SETTINGS = {
	"request_delay": 0,
	"concurrent_requests": 1,
	"allowed_domains": [],
	"blocked_domains": [],
	"link_priorities": [],
	"skip_patterns": None,
}


class FakeSite:
	"""Canned responses for example.com URLs. The real SSRF guard, redirects and retries still run,
	but no request leaves the machine. Unknown URLs answer 404."""

	def __init__(self, test_case, **settings):
		self.responses: dict[str, tuple[int, dict, bytes]] = {}
		self.requested: list[str] = []
		test_case.enterContext(patch("socket.getaddrinfo", side_effect=resolve))
		test_case.enterContext(
			patch(
				"urllib3.connectionpool.HTTPConnectionPool._make_request",
				autospec=True,
				side_effect=self.dispatch,
			)
		)
		test_case.enterContext(patch("urllib3.util.retry.time.sleep"))
		test_case.enterContext(change_settings("Web Crawl Settings", {**NEUTRAL_SETTINGS, **settings}))

	def add(self, url: str, body: str | bytes = "", content_type: str = HTML, status: int = 200, **headers):
		body = body.encode() if isinstance(body, str) else body
		self.responses[url] = (status, {"Content-Type": content_type, **headers}, body)

	def page(self, url: str, body: str, title: str = ""):
		self.add(url, f"<html><head><title>{title}</title></head><body>{body}</body></html>")

	def redirect(self, url: str, location: str, status: int = 301):
		self.add(url, status=status, Location=location)

	def dispatch(self, *args, **kwargs):
		"""Looks `respond` up per request, so a test can replace it."""
		return self.respond(*args, **kwargs)

	def respond(self, pool, connection, method, path, *args, **kwargs):
		url = f"{pool.scheme}://{pool.host}{path}"
		self.requested.append(url)
		status, headers, body = self.responses.get(url, (404, {"Content-Type": HTML}, b"not found"))
		return HTTPResponse(body=BytesIO(body), status=status, headers=headers, preload_content=False)


def resolve(host, port, *args, **kwargs):
	try:
		socket.inet_aton(host)
		address = host
	except OSError:
		address = PUBLIC_ADDRESS
	return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port or 0))]


def block_domain(test_case, domain: str):
	add_setting_row(test_case, "blocked_domains", {"domain": domain})


def allow_domain(test_case, domain: str):
	add_setting_row(test_case, "allowed_domains", {"domain": domain})


def add_setting_row(test_case, fieldname: str, row: dict):
	"""Adds a row to a Web Crawl Settings table until the test ends."""
	settings = frappe.get_doc("Web Crawl Settings")
	settings.append(fieldname, row)
	settings.save()
	test_case.addCleanup(clear_table, fieldname)


def clear_table(fieldname: str):
	settings = frappe.get_doc("Web Crawl Settings")
	settings.set(fieldname, [])
	settings.save()
