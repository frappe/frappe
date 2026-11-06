"""Read and write page scripts.

Every page script is an ES module that exports `setup(context)` as its default.
The function returns values and functions for `{{ }}` expressions and event handlers.
It can import other modules and read page variables, resources, route and router
from `context`.

The app type determines where a script is saved and how updates reach the running app:
- Database apps save to the page's `script` field. A reload event updates the canvas.
- Repository apps save to a companion `<page>.js` file. Writing requires developer
  mode and System Manager permissions. The write queues an app build; the agent must
  tell the user to wait for it.

Both write paths run on the server and update the app's source before requesting
a reload or build.
"""

import os

import frappe
from frappe.studio.ai.agent.registry import Tool
from frappe.studio.ai.agent.tools.page import load_page, save_page
from frappe.studio.export import can_export, write_code_file
from frappe.studio.utils import find_script_file, script_extension


def run_get_page_script(ctx, args: dict) -> str:
	page = load_page(ctx)
	if page is None:
		return "No page in context."
	source = _read_script(page)
	if not source.strip():
		return "This page has no script yet."
	where = "code file (<page>.js)" if can_export(page) else "the page's `script` field (DB)"
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
	"""Save a database app's page script and request a canvas reload."""
	if not frappe.has_permission("Studio Page", "write", page.name):
		return "FAILED: you do not have permission to edit this page."
	page.script = source
	if error := save_page(page):
		return f"FAILED: {error}"
	ctx.emit("reload", script=True)
	return "Updated the page script. It runs live on the canvas now."


def _write_file_script(ctx, page, source: str) -> str:
	"""Write a repository app's page script and queue an app build.

	Writing requires developer mode and System Manager permissions. The running app
	uses the new script after the build completes.
	"""
	if not frappe.conf.developer_mode:
		return (
			"FAILED: this page belongs to a repository app — its script lives in a code file editable "
			"only in developer mode. Ask a developer to enable it."
		)
	if "System Manager" not in frappe.get_roles():
		return "FAILED: writing a repository app's page script requires the System Manager role."
	# write_code_file reads the field from this object. Do not save the document:
	# repository page scripts belong in the code file, not the database field.
	page.script = source
	folder = page.get_folder_path()
	frappe.create_folder(folder)
	stem = page.get_export_docname()
	write_code_file(
		page, folder, code_field="script", extension=script_extension(folder, stem), filename=stem
	)
	frappe.enqueue_doc("Studio App", page.studio_app, "build_app_bundle", queue="long", timeout=1200)
	return (
		"Wrote the page script to its code file and started an app rebuild. The change appears on the "
		"canvas only after the build finishes — tell the user to wait for the rebuild to complete."
	)


def _read_script(page) -> str:
	if can_export(page):
		path = find_script_file(page.get_folder_path(), page.get_export_docname())
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
