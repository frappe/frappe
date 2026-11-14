import asyncio
import functools
import importlib
import ipaddress
import socket

import httpx
import pytest

from flow_harness.tools.tool import ToolContext

web_fetch_module = importlib.import_module("flow_harness.tools.bundled.web_fetch")
web_fetch = web_fetch_module.web_fetch

DNS = {"site.test": "93.184.216.34", "inner.test": "10.0.0.5", "metadata.test": "169.254.169.254"}
PAGE = (
	b"<html><head><title>T</title><script>var secret = 1</script></head><body>"
	b"<nav>Menu</nav><h1>Doc</h1><p>See <a href='/next'>next</a>.</p>"
	b"<table><tr><th>Plan</th></tr><tr><td>Pro</td></tr></table><footer>Legal</footer></body></html>"
)


@pytest.fixture
async def web(monkeypatch):
	"""Fake DNS and HTTP: `routes` maps a host to its response; `seen` records each request."""
	routes: dict[str, httpx.Response] = {}
	seen: list[httpx.Request] = []

	async def getaddrinfo(host, port, **kwargs):
		try:
			address = str(ipaddress.ip_address(host))
		except ValueError:
			if host not in DNS:
				raise socket.gaierror(host) from None
			address = DNS[host]
		return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

	def handle(request: httpx.Request) -> httpx.Response:
		seen.append(request)
		return routes[request.headers["host"]]

	monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
	monkeypatch.setattr(
		web_fetch_module.httpx,
		"AsyncClient",
		functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(handle)),
	)
	return routes, seen


async def test_web_fetch_turns_html_into_markdown(web):
	routes, seen = web
	routes["site.test"] = httpx.Response(200, content=PAGE, headers={"content-type": "text/html"})

	result = await web_fetch(url="https://site.test/doc", ctx=ToolContext())

	assert not result.is_error
	assert "# Doc" in result.content
	assert "[next](https://site.test/next)" in result.content
	assert "| Pro |" in result.content
	for dropped in ("secret", "Menu", "Legal"):
		assert dropped not in result.content
	# it connected to the address it checked, naming the host for TLS and virtual hosting
	assert seen[0].url.host == DNS["site.test"]
	assert seen[0].headers["host"] == "site.test"


async def test_web_fetch_refuses_private_addresses(web):
	routes, seen = web
	routes["site.test"] = httpx.Response(302, headers={"location": "http://metadata.test/latest"})

	for url in (
		"http://inner.test/",
		"http://127.0.0.1:8000/",
		"http://[::ffff:127.0.0.1]/",
		"file:///etc/passwd",
		"https://site.test/redirect",
	):
		result = await web_fetch(url=url, ctx=ToolContext())
		assert result.is_error, url
	# only the redirect's first hop was public, so it is the only request sent
	assert [request.headers["host"] for request in seen] == ["site.test"]


async def test_web_fetch_reports_what_it_cannot_read(web):
	routes, _ = web
	shell = b"<html><body><div id='root'></div><script src='/app.js'></script></body></html>"
	for content_type, body, expected, is_error in (
		("text/html", shell, "without JavaScript", False),
		("image/png", b"\x89PNG", "image/png, not text", True),
		("application/json", b'{"a": 1}', '{"a": 1}', False),
	):
		routes["site.test"] = httpx.Response(200, content=body, headers={"content-type": content_type})
		result = await web_fetch(url="https://site.test/", ctx=ToolContext())
		assert expected in result.content, content_type
		assert result.is_error is is_error, content_type
