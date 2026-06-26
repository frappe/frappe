import json
import re

import frappe


def execute():
	"""Migrate the removed "Switch App Page", "Open Webpage" and "Call API" event actions to "Run Script".

	These built-in actions were dropped in favour of scripts, so existing events are
	rewritten to equivalent router.push / window.open / call() calls.
	"""
	Page = frappe.qb.DocType("Studio Page")
	pages = (
		frappe.qb.from_(Page)
		.select(Page.name, Page.blocks, Page.draft_blocks)
		.where(
			Page.blocks.like("%Switch App Page%")
			| Page.draft_blocks.like("%Switch App Page%")
			| Page.blocks.like("%Open Webpage%")
			| Page.draft_blocks.like("%Open Webpage%")
			| Page.blocks.like("%Call API%")
			| Page.draft_blocks.like("%Call API%")
		)
		.run(as_dict=True)
	)

	for page in {p.name: p for p in pages}.values():
		updates = {}
		for field in ("blocks", "draft_blocks"):
			blocks = frappe.parse_json(page.get(field) or "[]")
			if blocks and migrate_blocks(blocks):
				updates[field] = frappe.as_json(blocks)
		if updates:
			frappe.get_doc("Studio Page", page.name).update(updates).save()

	components = frappe.get_all("Studio Component", fields=["name", "block"])
	for component in components:
		if not component.get("block"):
			continue
		block = frappe.parse_json(component.get("block"))
		if migrate_blocks([block]):
			frappe.get_doc("Studio Component", component.name).update({"block": frappe.as_json(block)}).save()


def migrate_blocks(blocks):
	"""Recursively rewrite legacy event actions. Returns True if anything changed."""
	changed = False
	for block in blocks:
		for event in (block.get("componentEvents") or {}).values():
			if migrate_event(event):
				changed = True

		if block.get("children"):
			changed = migrate_blocks(block["children"]) or changed

		for slot in (block.get("componentSlots") or {}).values():
			content = slot.get("slotContent") if slot else None
			if isinstance(content, list):
				changed = migrate_blocks(content) or changed

	return changed


def migrate_event(event):
	action = event.get("action")
	if action == "Switch App Page":
		event["script"] = f"router.push({json.dumps(event.get('page') or '')})"
		stale_fields = ("page",)
	elif action == "Open Webpage":
		event["script"] = f"window.open({json.dumps(event.get('url') or '')})"
		stale_fields = ("url",)
	elif action == "Call API":
		event["script"] = build_call_script(event)
		# success/error callbacks are now inlined into the script; these fields are
		# Call-API-specific here and must not be touched for "Insert a Document" events
		stale_fields = (
			"api_endpoint",
			"params",
			"on_success",
			"success_message",
			"on_success_script",
			"on_error",
			"error_message",
			"on_error_script",
		)
	else:
		return False

	event["action"] = "Run Script"
	for field in stale_fields:
		event.pop(field, None)
	return True


def build_call_script(event):
	"""Rebuild a Call API event as a call() script with its success/error callbacks.

	Note: the old runtime had a shortcut where an endpoint matching a registered
	resource called `resource.submit()` instead of issuing a fresh request. That path
	is not reproduced here; every Call API event becomes a plain `call(endpoint, params)`,
	which matches the common (non-resource) behaviour.
	"""
	args = json.dumps(event.get("api_endpoint") or "")
	params = event.get("params") or {}
	if params:
		args += f", {params_to_object_literal(params)}"

	script = f"call({args})"
	if success := callback_body(event, "success"):
		script += f"\n\t.then((data) => {{\n\t\t{success}\n\t}})"
	if error := callback_body(event, "error"):
		script += f"\n\t.catch((error) => {{\n\t\t{error}\n\t}})"
	return script


def callback_body(event, kind):
	arg, fn = ("data", "onSuccess") if kind == "success" else ("error", "onError")
	if event.get(f"on_{kind}") == "script" and event.get(f"on_{kind}_script"):
		return f"{event[f'on_{kind}_script']}\n\t\treturn {fn}({arg});"

	message = event.get("success_message" if kind == "success" else "error_message")
	if message:
		toast_fn = "toast.success" if kind == "success" else "toast.error"
		return f"{toast_fn}({json.dumps(message)});"
	return None


def params_to_object_literal(params):
	entries = ", ".join(
		f"{json.dumps(key)}: {value_to_js_expression(value)}" for key, value in params.items()
	)
	return f"{{ {entries} }}"


SINGLE_EXPRESSION = re.compile(r"^\s*\{\{(.+?)\}\}\s*$", re.DOTALL)
EMBEDDED_EXPRESSION = re.compile(r"\{\{(.+?)\}\}")


def value_to_js_expression(value):
	"""Convert a stored param value (literal or {{ }} template) to a JS expression."""
	if not isinstance(value, str):
		return json.dumps(value)

	single = SINGLE_EXPRESSION.match(value)
	if single:
		return single.group(1).strip()

	if EMBEDDED_EXPRESSION.search(value):
		template = value.replace("`", "\\`")
		template = EMBEDDED_EXPRESSION.sub(lambda m: "${" + m.group(1).strip() + "}", template)
		return f"`{template}`"

	return json.dumps(value)
