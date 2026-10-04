"""Router-script tools for a custom (non-exported) app, whose router config is the Studio App's
`router_script` field. An exported app keeps it in `router.ts`, written with write_app_file."""

import re

import frappe

from studio.ai.agent.registry import Tool
from studio.ai.agent.tools.page import load_page


def run_get_router_script(ctx, args: dict) -> str:
	app = load_app(ctx)
	if isinstance(app, str):
		return app
	if not app.router_script:
		return "This app has no router script yet; Studio's default routing applies."
	return f"Current router script:\n{app.router_script}"


def run_set_router_script(ctx, args: dict) -> str:
	source = (args.get("script") or "").strip()
	if error := get_script_error(source):
		return f"FAILED: {error}"
	app = load_app(ctx)
	if isinstance(app, str):
		return app
	if not frappe.has_permission("Studio App", "write", app.name):
		return "FAILED: you do not have permission to edit this app."
	app.router_script = source
	app.save()
	frappe.db.commit()
	ctx.emit("reload", router=True)
	return (
		"Saved the router script. It applies when the app loads, so tell the user to reload the "
		"preview to check it; a script that throws stops the app on an error page."
	)


def load_app(ctx):
	"""The page's Studio App, or a FAILED string when it is missing or exported."""
	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	if page.is_standard:
		return "FAILED: this app is exported — its router lives in `router.ts`; edit it with write_app_file."
	return frappe.get_doc("Studio App", page.studio_app)


def get_script_error(source: str) -> str | None:
	if not source:
		return "script is required — pass the FULL object literal, not a fragment."
	if re.search(r"(?m)^\s*(export|import)\b", source):
		return "a custom app's router script has no `export`/`import` — pass just the object literal `{ … }`."
	if not source.startswith("{"):
		return (
			"the router script is one object literal: `{ routerOptions, extendRoute(route), setup(router) }`."
		)
	return None


get_router_script = Tool(
	name="get_router_script",
	side="server",
	handler=run_get_router_script,
	description=(
		"Read the app's router script. Call this before set_router_script so you extend it instead of "
		"overwriting it — set_router_script replaces the whole script."
	),
	parameters={"type": "object", "properties": {}},
)

set_router_script = Tool(
	name="set_router_script",
	side="server",
	handler=run_set_router_script,
	description=(
		"Author the app's router script: ONE object literal with optional keys routerOptions, "
		"extendRoute(route) and setup(router) — no `export`, no `import`. It is plain vue-router (see "
		"Navigation & app-wide routing). Pass the ENTIRE script; read it first with get_router_script."
	),
	parameters={
		"type": "object",
		"properties": {
			"script": {
				"type": "string",
				"description": (
					'The FULL object literal, e.g. \'{ extendRoute(route) { if (route.name === "Tasks") '
					'route.alias = "/todo" }, setup(router) { router.addRoute({ path: "/old-tasks", '
					'redirect: { name: "Tasks" } }) } }\'.'
				),
			}
		},
		"required": ["script"],
	},
)

TOOLS = [get_router_script, set_router_script]
