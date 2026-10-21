import json
import re

import frappe
from frappe import _
from json_repair import repair_json


class BlockCodec:
	@staticmethod
	def compress(block: dict, depth: int = 0) -> dict:
		if not isinstance(block, dict):
			return block

		out = {}

		if cid := block.get("componentId"):
			out["id"] = cid
		if name := block.get("componentName"):
			out["name"] = name
		if orig := block.get("originalElement"):
			out["originalElement"] = orig
		if block.get("blockName"):
			out["label"] = block["blockName"]

		props = {k: v for k, v in (block.get("componentProps") or {}).items() if v not in (None, "", [], {})}
		if props:
			out["props"] = props

		style = block.get("baseStyles") or {}
		if style:
			out["style"] = style

		mob = block.get("mobileStyles") or {}
		if mob:
			out["mstyle"] = mob

		tab = block.get("tabletStyles") or {}
		if tab and depth <= 1:
			out["tstyle"] = tab

		if compact_slots := BlockCodec._compress_slots(block.get("componentSlots") or {}, depth):
			out["slots"] = compact_slots

		events = block.get("componentEvents") or {}
		if events:
			out["events"] = BlockCodec._compress_events(events)
		if vis := block.get("visibilityCondition"):
			out["visibility"] = vis

		children = [
			BlockCodec.compress(c, depth + 1) for c in block.get("children", []) if isinstance(c, dict)
		]
		if children:
			out["c"] = children

		return out

	@staticmethod
	def _compress_slots(slots: dict, depth: int) -> dict:
		"""Compact componentSlots to {slotName: [compact blocks]}. Slot children use the SAME
		compact shape as `c` (recurse), and the derived slotId/parentBlockId are dropped (the
		client regenerates them). Empty slots are omitted."""
		out = {}
		for name, slot in slots.items():
			if not isinstance(slot, dict):
				continue
			content = slot.get("slotContent")
			if isinstance(content, list):
				blocks = [BlockCodec.compress(b, depth + 1) for b in content if isinstance(b, dict)]
				if blocks:
					out[name] = blocks
		return out

	@staticmethod
	def _expand_slots(slots: dict) -> dict:
		"""Expand compact slots ({slotName: [blocks]}) into componentSlots. slotId/
		parentBlockId are backfilled by the frontend Block constructor (initializeSlots)."""
		out = {}
		if not isinstance(slots, dict):
			return out
		for name, content in slots.items():
			if not isinstance(content, list):
				continue
			slot_content = [BlockCodec.expand(b) for b in content if isinstance(b, dict)]
			out[name] = {"slotName": name, "slotContent": slot_content}
		return out

	@staticmethod
	def _compress_events(events: dict) -> dict:
		"""Compact componentEvents for the page context. A 'Run Script' handler collapses to
		just its script string (the common case); other action shapes pass through verbatim."""
		out = {}
		for name, ev in events.items():
			if isinstance(ev, dict) and ev.get("action") == "Run Script":
				out[name] = ev.get("script") or ""
			else:
				out[name] = ev
		return out

	@staticmethod
	def expand(node: dict) -> dict:
		if not isinstance(node, dict):
			return node

		block: dict = {
			"componentName": node.get("name", "container"),
			"baseStyles": node.get("style") or {},
			"componentProps": node.get("props") or {},
			"componentSlots": BlockCodec._expand_slots(node.get("slots") or {}),
			"mobileStyles": node.get("mstyle") or {},
			"tabletStyles": node.get("tstyle") or {},
			"children": [BlockCodec.expand(c) for c in node.get("c", []) if isinstance(c, dict)],
		}

		if cid := node.get("id"):
			block["componentId"] = cid
		if orig := node.get("originalElement"):
			block["originalElement"] = orig
		if label := node.get("label"):
			block["blockName"] = label
		if events := node.get("events"):
			block["componentEvents"] = BlockCodec._expand_events(events)
		if vis := node.get("visibility"):
			block["visibilityCondition"] = vis

		return block

	@staticmethod
	def _expand_events(events: dict) -> dict:
		"""Expand the compact `events` map (eventName → script, or → full object) into Studio
		componentEvents. A bare string is a 'Run Script' handler."""
		out = {}
		if not isinstance(events, dict):
			return out
		for name, val in events.items():
			if isinstance(val, str):
				out[name] = {"event": name, "action": "Run Script", "script": val}
			elif isinstance(val, dict):
				ev = dict(val)
				ev.setdefault("event", name)
				ev.setdefault("action", "Run Script")
				out[name] = ev
		return out

	@staticmethod
	def parse_blocks(content: str) -> dict:
		cleaned = BlockCodec.strip_fences(content)
		try:
			parsed = json.loads(cleaned, strict=False)
		except json.JSONDecodeError:
			parsed = repair_json(cleaned, return_objects=True)

		if isinstance(parsed, list):
			block = parsed[0] if parsed else {}
		elif isinstance(parsed, dict):
			block = parsed
		else:
			raise ValueError("LLM response is not a valid block object")

		if not block:
			raise ValueError("LLM response produced an empty block")

		if isinstance(block, dict) and not block.get("id"):
			block["id"] = "root"

		return BlockCodec.expand(block)

	@staticmethod
	def to_json(data) -> str:
		"""Compact, token-efficient JSON: no whitespace, unicode kept as-is."""
		return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

	@staticmethod
	def strip_fences(text: str) -> str:
		text = re.sub(r"^```(?:json|yaml)?\s*\n?", "", text.strip())
		return re.sub(r"\n?```\s*$", "", text).strip()

	@staticmethod
	def validate_image_data(image_data: str) -> str:
		"""Validate a base64 image data URL sent with a prompt (a screenshot/design to reproduce).
		Cap the encoded string at 7 MB — base64 inflates ~33%, so that's roughly a 5 MB source image."""
		if not image_data.startswith("data:image/"):
			frappe.throw(_("Invalid image data: must be a base64-encoded image data URL"))
		if ";base64," not in image_data:
			frappe.throw(_("Invalid image data: must be a base64-encoded data URL"))
		if len(image_data) > 7 * 1024 * 1024:
			frappe.throw(_("Image is too large. Please use an image smaller than 5 MB."))
		return image_data
