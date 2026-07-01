import json
import re

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

		raw = block.get("rawStyles") or {}
		if raw:
			out["rstyle"] = raw

		mob = block.get("mobileStyles") or {}
		if mob:
			out["mstyle"] = mob

		tab = block.get("tabletStyles") or {}
		if tab and depth <= 1:
			out["tstyle"] = tab

		slots = block.get("componentSlots") or {}
		if slots:
			out["slots"] = slots

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
			"rawStyles": node.get("rstyle") or {},
			"componentProps": node.get("props") or {},
			"componentSlots": node.get("slots") or {},
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
	def strip_context(block_json: str) -> str:
		"""Compress a block to compact JSON for LLM context, extracting relevant subset."""
		try:
			data = json.loads(block_json)
		except (json.JSONDecodeError, TypeError):
			return block_json

		if isinstance(data, list):
			data = data[0] if data else {}
		if not isinstance(data, dict):
			return block_json

		return BlockCodec.to_json(BlockCodec.compress(data))

	@staticmethod
	def to_json(data) -> str:
		"""Compact, token-efficient JSON: no whitespace, unicode kept as-is."""
		return json.dumps(data, separators=(",", ":"), ensure_ascii=False)

	@staticmethod
	def strip_fences(text: str) -> str:
		text = re.sub(r"^```(?:json|yaml)?\s*\n?", "", text.strip())
		return re.sub(r"\n?```\s*$", "", text).strip()
