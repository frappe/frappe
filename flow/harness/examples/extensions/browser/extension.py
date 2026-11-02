"""A tool whose dependency is not one of Flow's.

Playwright is installed into the environment that runs `flow serve`, never added to
Flow's own pyproject.toml:

    ./env/bin/pip install playwright
    ./env/bin/playwright install chromium

Run with:

    flow -e examples/extensions/browser
"""

from flow_harness.extensions import ExtensionAPI
from flow_harness.tools import ToolContext, ToolResult, tool

MISSING = "playwright is not installed in the daemon environment (pip install playwright)"


@tool(prompt_snippet="Screenshot a web page", display_template="Opening {{ url }}")
async def screenshot(url: str, *, ctx: ToolContext) -> ToolResult:
	"""Capture a PNG of a web page."""
	# imported per call, so a missing package costs one call instead of the whole extension
	try:
		from playwright.async_api import async_playwright
	except ImportError:
		return ToolResult(content=MISSING, is_error=True)

	async with async_playwright() as playwright:
		browser = await playwright.chromium.launch()
		try:
			page = await browser.new_page()
			await page.goto(url, timeout=ctx.timeout * 1000)
			png = await page.screenshot()
		finally:
			await browser.close()

	if ctx.store_image is None:
		return ToolResult(content=f"[captured {len(png)} bytes from {url}]")
	image = await ctx.store_image("screenshot.png", png)
	return ToolResult(content=f"[screenshot of {url}]", attachments=[image])


def setup(flow: ExtensionAPI) -> None:
	flow.register_tool(screenshot)
