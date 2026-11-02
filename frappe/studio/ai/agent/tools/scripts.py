"""Page-script tools — read and author a page's client script.

Every page's script is an ES module whose default export is a `setup(context)` function
returning the bindings `{{ }}` expressions and event handlers use. It may `import`, and
reads the page's variables, resources, route and router off `context`.

Where that script LIVES differs by app, and so do the two write paths:
  - Database app → the DB `script` field, compiled in the browser. Editing it is live:
    the canvas re-runs setup() as soon as the change is saved (reload event).
  - Repository app in developer mode → a companion `<page>.ts` code file on disk
    (`can_export`). The running app only reflects it after `generate_app_build`
    rebuilds the bundle, so the write enqueues a build and the model must tell the
    user to wait. Outside developer mode this file can't be written — refused.

Both are server-side: the handler mutates the store of record, then either emits a
reload (DB path) or enqueues a build (file path).
"""

import os

import frappe
from frappe.studio.ai.agent.registry import Tool
from frappe.studio.ai.agent.tools.page import load_page, save_page
from frappe.studio.export import can_export, write_code_file


def run_get_page_script(ctx, args: dict) -> str:
	page = load_page(ctx)
	if page is None:
		return "No page in context."
	source = _read_script(page)
	if not source.strip():
		return "This page has no script yet."
	where = "code file (<page>.ts)" if can_export(page) else "the page's `script` field (DB)"
	return f"Current page script (stored in {where}):\n{source}"


def run_set_page_script(ctx, args: dict) -> str:
	source = args.get("script")
	if not isinstance(source, str) or not source.strip():
		return "FAILED: script is required — pass the FULL script, not a fragment."
	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	if "export default" not in source:
		return (
			"FAILED: a page script is an ES module — its default export must be "
			"`export default function setup(context) { … return { … } }`. Only what you return becomes "
			"a binding."
		)
	if page.is_standard:
		return _write_file_script(ctx, page, source)
	return _write_db_script(ctx, page, source)


# --- write paths ----------------------------------------------------------


def _write_db_script(ctx, page, source: str) -> str:
	"""Database app: store the script in the DB and reload the canvas — live."""
	if not frappe.has_permission("Studio Page", "write", page.name):
		return "FAILED: you do not have permission to edit this page."
	page.script = source
	if error := save_page(page):
		return f"FAILED: {error}"
	ctx.emit("reload", script=True)
	return "Updated the page script. It runs live on the canvas now."


def _write_file_script(ctx, page, source: str) -> str:
	"""Repository app: the script is a code file. Only writable in developer mode by a
	System Manager; the running app reflects it only after the app rebuilds."""
	if not frappe.conf.developer_mode:
		return (
			"FAILED: this page belongs to a repository app — its script lives in a code file editable "
			"only in developer mode. Ask a developer to enable it."
		)
	if "System Manager" not in frappe.get_roles():
		return "FAILED: writing a repository app's page script requires the System Manager role."
	# Feed write_code_file via the in-memory field; the DB `script` stays null (the .ts is
	# the source of truth for a repository app's page), so we deliberately do NOT save the doc.
	page.script = source
	folder = page.get_folder_path()
	frappe.create_folder(folder)
	write_code_file(page, folder, code_field="script", extension="ts", filename=page.get_export_docname())
	frappe.enqueue_doc("Studio App", page.studio_app, "build_app_bundle", queue="long", timeout=1200)
	return (
		"Wrote the page script to its code file and started an app rebuild. The change appears on the "
		"canvas only after the build finishes — tell the user to wait for the rebuild to complete."
	)


def _read_script(page) -> str:
	if can_export(page):
		path = os.path.join(page.get_folder_path(), f"{page.get_export_docname()}.ts")
		return frappe.read_file(path) or "" if os.path.exists(path) else ""
	return page.script or ""


# --- tool definitions -----------------------------------------------------

get_page_script = Tool(
	name="get_page_script",
	side="server",
	handler=run_get_page_script,
	description=(
		"Read the page's current script. Call this before set_page_script so you EXTEND the existing "
		"script instead of overwriting it — set_page_script replaces the whole thing."
	),
	parameters={"type": "object", "properties": {}},
)

set_page_script = Tool(
	name="set_page_script",
	side="server",
	handler=run_set_page_script,
	description=(
		"Author the page's setup() module. The default export MUST be `export default function "
		"setup(context) { … return { … } }`. It is a real module, so IMPORT framework APIs at the top: "
		"`import { ref, computed, watch } from 'vue'` (also 'frappe-ui', 'pinia', 'vue-router', and the "
		"app's own files via '@app/*'). `ref`/`computed` are NOT on `context` — never write `context.ref` "
		"or `const { ref } = context`; import them from 'vue'. The `context` param carries the PAGE's own "
		"things — its data sources/resources, variables, `route` and `router` (e.g. `context.notes`, "
		"`context.route`). Only what you RETURN becomes bindings usable in {{ }} and handlers. Pass the "
		"ENTIRE module (it replaces the current one; read it first with get_page_script)."
	),
	parameters={
		"type": "object",
		"properties": {
			"script": {
				"type": "string",
				"description": (
					'The FULL module source, e.g. \'import { computed } from "vue"\\nexport default '
					"function setup(context) { const total = computed(() => context.items.data.length); "
					"return { total } }'."
				),
			}
		},
		"required": ["script"],
	},
)

TOOLS = [get_page_script, set_page_script]
