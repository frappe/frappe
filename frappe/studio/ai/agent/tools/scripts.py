"""Page-script tools — read and author a page's client script.

A page's script exposes top-level bindings — refs, computed, functions — usable in
`{{ }}` expressions and event handlers. It has TWO forms depending on whether the
app is exported, and set_page_script serves both (build_tools picks the description):

  - Non-exported page → a bare `<script setup>` body (no `export`/`import`/`setup()`),
    interpreted live. Top-level declarations are auto-exposed; Vue APIs, variables,
    resources, route and router are ambient (write `ref(0)`, not `context.ref`).
  - Standard (exported) page → a real ES module whose default export is a
    `setup(context)` function returning its bindings; it may `import`, and reads
    variables/resources/route/router off `context`.

Where that script LIVES also differs, and the two write paths differ:
  - Non-standard page → the DB `script` field. Editing it is live: the canvas
    re-runs setup() as soon as the change is saved (reload event).
  - Standard page in developer mode → a companion `<page>.ts` code file on disk
    (`can_export`). The running app only reflects it after `generate_app_build`
    rebuilds the bundle, so the write enqueues a build and the model must tell the
    user to wait. Outside developer mode this file can't be written — refused.

Both are server-side: the handler mutates the store of record, then either emits a
reload (DB path) or enqueues a build (file path).
"""

import os
import re

import frappe

from studio.ai.agent.registry import Tool
from studio.ai.agent.tools.page import load_page, save_page
from studio.export import can_export, write_code_file


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
	if page.is_standard:
		if "export default" not in source:
			return (
				"FAILED: a standard (exported) page's script is an ES module — its default export must be "
				"`export default function setup(context) { … return { … } }`. Only what you return becomes "
				"a binding."
			)
		return _write_file_script(ctx, page, source)
	if _is_module_source(source):
		return (
			"FAILED: a custom (non-exported) page's script is a bare <script setup> body — remove "
			"`export`/`import`/the `setup()` wrapper. Declare state at the top level (every top-level "
			"const/function is auto-exposed to {{ }}); use ref/computed/route directly, not context.x."
		)
	return _write_db_script(ctx, page, source)


# --- write paths ----------------------------------------------------------


def _write_db_script(ctx, page, source: str) -> str:
	"""Non-standard page: store the script in the DB and reload the canvas — live."""
	if not frappe.has_permission("Studio Page", "write", page.name):
		return "FAILED: you do not have permission to edit this page."
	page.script = source
	if error := save_page(page):
		return f"FAILED: {error}"
	ctx.emit("reload", script=True)
	return "Updated the page script. It runs live on the canvas now."


def _write_file_script(ctx, page, source: str) -> str:
	"""Standard page: the script is a code file. Only writable in developer mode by a
	System Manager; the running app reflects it only after the app rebuilds."""
	if not frappe.conf.developer_mode:
		return (
			"FAILED: this is a standard page — its script lives in a code file editable only in "
			"developer mode. Do this on a non-standard page, or ask a developer to enable it."
		)
	if "System Manager" not in frappe.get_roles():
		return "FAILED: writing a standard page's script requires the System Manager role."
	# Feed write_code_file via the in-memory field; the DB `script` stays null (the .ts is
	# the source of truth for a standard page), so we deliberately do NOT save the doc.
	page.script = source
	folder = page.get_folder_path()
	frappe.create_folder(folder)
	write_code_file(page, folder, code_field="script", extension="ts", filename=page.get_export_docname())
	frappe.enqueue_doc("Studio App", page.studio_app, "generate_app_build", queue="long", timeout=1200)
	return (
		"Wrote the page script to its code file and started an app rebuild. The change appears on the "
		"canvas only after the build finishes — tell the user to wait for the rebuild to complete."
	)


def _read_script(page) -> str:
	if can_export(page):
		path = os.path.join(page.get_folder_path(), f"{page.get_export_docname()}.ts")
		return frappe.read_file(path) or "" if os.path.exists(path) else ""
	return page.script or ""


def _is_module_source(source: str) -> bool:
	"""True if the source uses ES-module syntax (a top-level `export`/`import`) — the standard-page
	form. A custom page's script is interpreted with `new Function` + `with`, where that syntax throws,
	so it must be a bare `<script setup>` body instead."""
	return bool(re.search(r"(?m)^\s*(export|import)\b", source))


# --- tool definitions -----------------------------------------------------
#
# The page script has two authoring forms that differ by whether the app is exported (see the module
# docstring). Both share the handlers above — the handler routes by `page.is_standard` — but the tool
# DESCRIPTION differs so the model writes the right form for the app it's in. build_tools() picks the
# form; the registry passes is_standard for the agent it's assembling.

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

_CUSTOM_SET_DESCRIPTION = (
	"Author the page's client script — a bare `<script setup>` body (NO `export`, NO `import`, NO "
	"`setup()` wrapper). For page logic that outgrows a single event handler: shared helpers, watchers, "
	"computed values, data fetched on mount. Declare state and helpers at the TOP LEVEL and every "
	"top-level const/function is auto-exposed to {{ }} and handlers — do NOT write a return. Vue "
	"reactivity APIs (ref/computed/watch), the page's variables, resources, route and router are all "
	"directly in scope — write `ref(0)` and `route.params`, never `context.ref`. Pass the ENTIRE script "
	"(it replaces the current one; read it first with get_page_script). It runs live on the canvas once saved."
)

_STANDARD_SET_DESCRIPTION = (
	"Author the page's setup() module — a real ES module in the exported app. The default export MUST be "
	"`export default function setup(context) { … return { … } }`. `import` from 'vue', 'frappe-ui', or "
	"the app's own files via '@app/*' (stores, composables, utils). Only what you RETURN becomes bindings "
	"usable in {{ }} and handlers; `context` exposes the page's variables, resources, route and router "
	"(e.g. context.computed(...), context.route). Pass the ENTIRE module (it replaces the current one; "
	"read it first with get_page_script). Saving rebuilds the app bundle — tell the user to wait for the build."
)


def build_tools(is_standard: bool) -> list[Tool]:
	"""Page-script tools for one agent. get_page_script is shared; set_page_script's description (and
	example) match the app's script form so the model writes bare vs. setup() correctly."""
	if is_standard:
		description = _STANDARD_SET_DESCRIPTION
		example = "export default function setup(context) { const total = context.computed(() => items.value.length); return { total } }"
	else:
		description = _CUSTOM_SET_DESCRIPTION
		example = "const total = computed(() => items.value.length)  // auto-exposed as {{ total }}"

	set_page_script = Tool(
		name="set_page_script",
		side="server",
		handler=run_set_page_script,
		description=description,
		parameters={
			"type": "object",
			"properties": {
				"script": {"type": "string", "description": f"The FULL script source, e.g. '{example}'."}
			},
			"required": ["script"],
		},
	)
	return [get_page_script, set_page_script]


# Default (custom/non-exported) tools for callers that don't specify a mode.
TOOLS = build_tools(is_standard=False)
