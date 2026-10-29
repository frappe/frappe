import functools
import importlib

import httpx
import pytest
from pydantic import ValidationError

from flow_harness.session.config import WebSearchConfig
from flow_harness.tools.tool import ToolContext

web_search_module = importlib.import_module("flow_harness.tools.bundled.web_search")
web_search = web_search_module.web_search

DUCKDUCKGO_PAGE = """<html><body>
<div class="result results_links result--ad"><h2><a class="result__a" href="https://duckduckgo.com/y.js?ad=1">Ad</a></h2></div>
<div class="result results_links web-result"><h2 class="result__title">
<a rel="nofollow" class="result__a" href="https://frappe.io/framework">Frappe <b>Framework</b></a></h2>
<a class="result__snippet" href="https://frappe.io/framework">A <b>low code</b> framework.</a></div>
<div class="result results_links web-result"><h2 class="result__title">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Ffrappe%2Ffrappe&amp;rut=x">GitHub</a></h2></div>
</body></html>"""


@pytest.fixture
def web(monkeypatch):
	"""Fake HTTP: `routes` maps a host to its response; `seen` records each request."""
	routes: dict[str, httpx.Response] = {}
	seen: list[httpx.Request] = []

	def handle(request: httpx.Request) -> httpx.Response:
		seen.append(request)
		return routes[request.url.host]

	monkeypatch.setattr(
		web_search_module.httpx,
		"AsyncClient",
		functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(handle)),
	)
	return routes, seen


async def test_duckduckgo_needs_no_key_and_skips_ads(web):
	routes, seen = web
	routes["html.duckduckgo.com"] = httpx.Response(200, text=DUCKDUCKGO_PAGE)

	result = await web_search(query="frappe", ctx=ToolContext())

	assert not result.is_error
	assert result.content == (
		"1. Frappe Framework\nhttps://frappe.io/framework\nA low code framework.\n\n"
		"2. GitHub\nhttps://github.com/frappe/frappe"
	)
	assert seen[0].content == b"q=frappe"


async def test_duckduckgo_rate_limit_points_at_a_key(web):
	routes, _ = web
	routes["html.duckduckgo.com"] = httpx.Response(202, text="<html>challenge</html>")

	result = await web_search(query="frappe", ctx=ToolContext())

	assert result.is_error
	assert "API key" in result.content


@pytest.mark.parametrize(
	("provider", "host", "auth", "body"),
	[
		(
			"brave",
			"api.search.brave.com",
			("x-subscription-token", "k"),
			{
				"web": {
					"results": [
						{"title": "T", "url": "https://a.test", "description": "<strong>x</strong> &amp; y"}
					]
				}
			},
		),
		(
			"tavily",
			"api.tavily.com",
			("authorization", "Bearer k"),
			{"results": [{"title": "T", "url": "https://a.test", "content": "x & y"}]},
		),
		(
			"exa",
			"api.exa.ai",
			("x-api-key", "k"),
			{"results": [{"title": "T", "url": "https://a.test", "highlights": ["x & y"]}]},
		),
	],
)
async def test_keyed_providers_send_the_key_and_read_results(web, provider, host, auth, body):
	routes, seen = web
	routes[host] = httpx.Response(200, json=body)
	ctx = ToolContext(web_search=WebSearchConfig(provider=provider, api_key="k"))

	result = await web_search(query="q", ctx=ctx)

	assert result.content == "1. T\nhttps://a.test\nx & y"
	assert seen[0].headers[auth[0]] == auth[1]


async def test_a_refused_key_is_an_error(web):
	routes, _ = web
	routes["api.tavily.com"] = httpx.Response(401, json={"detail": "bad key"})
	ctx = ToolContext(web_search=WebSearchConfig(provider="tavily", api_key="wrong"))

	result = await web_search(query="q", ctx=ctx)

	assert result.is_error
	assert result.content == "[tavily answered HTTP 401]"


def test_a_keyed_provider_needs_its_key():
	with pytest.raises(ValidationError):
		WebSearchConfig(provider="brave")
