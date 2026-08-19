"""File tools — read and write an exported app's code files (stores, composables, utils, components).

Only for STANDARD (exported) apps: their frontend is a real TypeScript project on disk under
`<frappe_app>/studio/<studio_app>/`. These server tools wrap the jailed studio-file API in
studio.api, which already enforces the path jail, the editable-extension allowlist, developer mode
and the System Manager role — so the model never touches anything outside the app folder. A page
edits its own logic with set_page_script; these tools are for the SHARED code around it, imported
into page scripts via the app's `@app/*` alias.
"""

import frappe

from studio.ai.agent.registry import Tool
from studio.ai.agent.tools.page import load_page, text_arg


def run_list_app_files(ctx, args: dict) -> str:
	ref = _app_ref(ctx)
	if isinstance(ref, str):
		return ref
	from studio import api

	try:
		tree = api.list_studio_files(*ref)
	except Exception as error:
		return _fail(error)
	paths = _flatten(tree)
	if not paths:
		return "The app has no editable files yet. Create them with write_app_file (e.g. stores/notes.ts)."
	return "App files (paths are relative to the app root, imported as '@app/<path>'):\n" + "\n".join(paths)


def run_read_app_file(ctx, args: dict) -> str:
	ref = _app_ref(ctx)
	if isinstance(ref, str):
		return ref
	path = text_arg(args.get("file_path"))
	if not path:
		return "FAILED: file_path is required."
	from studio import api

	try:
		result = api.read_studio_file(*ref, path)
	except Exception as error:
		return _fail(error)
	return f"{path}:\n{result['content']}"


def run_write_app_file(ctx, args: dict) -> str:
	ref = _app_ref(ctx)
	if isinstance(ref, str):
		return ref
	path = text_arg(args.get("file_path"))
	content = args.get("content")
	if not path:
		return "FAILED: file_path is required."
	if not isinstance(content, str):
		return "FAILED: content is required (the full file text)."
	from studio import api

	try:
		api.write_studio_file(*ref, path, content)
	except Exception as error:
		return _fail(error)
	return (
		f"Wrote {path}. Import it from a page script via '@app/{path.rsplit('.', 1)[0]}'. "
		"Run trigger_app_build once your files are ready so the running app picks them up."
	)


def run_delete_app_file(ctx, args: dict) -> str:
	ref = _app_ref(ctx)
	if isinstance(ref, str):
		return ref
	path = text_arg(args.get("file_path"))
	if not path:
		return "FAILED: file_path is required."
	from studio import api

	try:
		api.delete_studio_file(*ref, path)
	except Exception as error:
		return _fail(error)
	return f"Deleted {path}."


def run_trigger_app_build(ctx, args: dict) -> str:
	ref = _app_ref(ctx)
	if isinstance(ref, str):
		return ref
	_, studio_app = ref
	frappe.enqueue_doc("Studio App", studio_app, "build_app_bundle", queue="long", timeout=1200)
	return (
		"Started an app rebuild. The file changes appear in the running app only after it finishes — "
		"tell the user to wait for the build to complete."
	)


# --- helpers --------------------------------------------------------------


def _app_ref(ctx) -> tuple[str, str] | str:
	"""(frappe_app, studio_app) for the page in context, or a FAILED string if it isn't an exported app."""
	page = load_page(ctx)
	if page is None:
		return "FAILED: no page in context."
	if not page.is_standard:
		return "FAILED: this app isn't exported — it has no code files. Use variables and set_page_script instead."
	return page.frappe_app, page.studio_app


def _flatten(nodes: list[dict]) -> list[str]:
	"""Depth-first list of paths from the file tree; folders get a trailing '/'."""
	paths = []
	for node in nodes:
		if node["is_folder"]:
			paths.append(node["path"] + "/")
			paths.extend(_flatten(node["children"]))
		else:
			paths.append(node["path"])
	return paths


def _fail(error: Exception) -> str:
	return f"FAILED: {error}"


# --- tool definitions -----------------------------------------------------

list_app_files = Tool(
	name="list_app_files",
	side="server",
	handler=run_list_app_files,
	description=(
		"List the exported app's editable code files (stores, composables, utils, components, page "
		"scripts). Use before read_app_file / write_app_file to see what already exists and reuse it."
	),
	parameters={"type": "object", "properties": {}},
)

read_app_file = Tool(
	name="read_app_file",
	side="server",
	handler=run_read_app_file,
	description="Read one of the exported app's code files. Read before editing so you extend it, not clobber it.",
	parameters={
		"type": "object",
		"properties": {
			"file_path": {
				"type": "string",
				"description": "Path relative to the app root, e.g. 'stores/notes.ts'.",
			}
		},
		"required": ["file_path"],
	},
)

write_app_file = Tool(
	name="write_app_file",
	side="server",
	handler=run_write_app_file,
	description=(
		"Create or overwrite one of the exported app's code files — a Pinia store, a composable, a util, "
		"or a custom component (.ts/.js/.vue/.css) for state or logic shared across pages. Parent folders "
		"are created automatically. Import it from a page's setup() module via '@app/<path-without-ext>'. "
		"Pass the ENTIRE file content (it overwrites; read_app_file first to extend an existing file). Run "
		"trigger_app_build afterwards so the change reaches the running app."
	),
	parameters={
		"type": "object",
		"properties": {
			"file_path": {
				"type": "string",
				"description": "Path relative to the app root, e.g. 'stores/notes.ts' or 'composables/useFilters.ts'.",
			},
			"content": {"type": "string", "description": "The full file content."},
		},
		"required": ["file_path", "content"],
	},
)

delete_app_file = Tool(
	name="delete_app_file",
	side="server",
	handler=run_delete_app_file,
	description="Delete one of the exported app's code files (Studio-generated page/component files are protected).",
	parameters={
		"type": "object",
		"properties": {
			"file_path": {
				"type": "string",
				"description": "Path relative to the app root, e.g. 'utils/old.ts'.",
			}
		},
		"required": ["file_path"],
	},
)

trigger_app_build = Tool(
	name="trigger_app_build",
	side="server",
	handler=run_trigger_app_build,
	description=(
		"Rebuild the exported app's bundle so file edits (stores/composables/utils) reach the running "
		"app. Call once after writing files. Tell the user the change appears only after the build finishes."
	),
	parameters={"type": "object", "properties": {}},
)

TOOLS = [list_app_files, read_app_file, write_app_file, delete_app_file, trigger_app_build]
