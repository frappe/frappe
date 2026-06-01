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

		children = [
			BlockCodec.compress(c, depth + 1) for c in block.get("children", []) if isinstance(c, dict)
		]
		if children:
			out["c"] = children

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

		return block

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
