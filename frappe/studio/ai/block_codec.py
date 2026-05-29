import re

import yaml


class CompactDumper(yaml.Dumper):
	"""Minimal-whitespace YAML dumper: indentless lists, flow style for flat dicts.
	Two optimizations over the default Dumper:
	1. indentless=True — removes the extra 2-space indent on list items inside
	   mappings, which compounds in deeply nested block trees.
	2. Flow style for flat dicts — turns multi-line style blocks into single-line
	   {k: v, k: v} inline mappings, saving ~60% of style-dict tokens.
	"""

	def increase_indent(self, flow=False, indentless=False):
		return super().increase_indent(flow=flow, indentless=True)

	def represent_mapping(self, tag, mapping, flow_style=None):
		if flow_style is None:
			flow_style = all(not isinstance(v, (dict | list)) for v in mapping.values())
		return super().represent_mapping(tag, mapping, flow_style=flow_style)


def _str_representer(dumper, data):
	"""Use plain scalars where safe; single-quote only when the value contains
	characters that would confuse the YAML parser."""
	unsafe = (":", "{", "}", "[", "]", "#", "&", "*", "!", "|", ">", "'", '"', "?", "\n")
	if any(c in data for c in unsafe):
		return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")
	return dumper.represent_scalar("tag:yaml.org,2002:str", data)


CompactDumper.add_representer(str, _str_representer)


def _to_yaml(data) -> str:
	return yaml.dump(
		data,
		Dumper=CompactDumper,
		sort_keys=False,
		default_flow_style=False,
		allow_unicode=True,
		width=1000,
	)


def _strip_fences(text: str) -> str:
	text = re.sub(r"^```(?:yaml|json)?\s*\n?", "", text.strip())
	return re.sub(r"\n?```\s*$", "", text).strip()


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
		cleaned = _strip_fences(content)
		parsed = yaml.safe_load(cleaned)

		if isinstance(parsed, list):
			node = parsed[0] if parsed else {}
		elif isinstance(parsed, dict):
			node = parsed
		else:
			raise ValueError("LLM response is not a valid block object")

		if not node:
			raise ValueError("LLM response produced an empty block")

		return BlockCodec.expand(node)

	@staticmethod
	def parse_partial(content: str) -> dict | None:
		"""Best-effort parse of a partial YAML stream. Returns None on failure."""
		if not content or not content.strip():
			return None
		try:
			cleaned = _strip_fences(content)
			parsed = yaml.safe_load(cleaned)
			if isinstance(parsed, list):
				node = parsed[0] if parsed else None
			elif isinstance(parsed, dict):
				node = parsed
			else:
				return None
			if not node or not isinstance(node, dict):
				return None
			if "name" not in node:
				return None
			return BlockCodec.expand(node)
		except yaml.YAMLError:
			return None

	@staticmethod
	def strip_context(block_json: str, task_type: str = "full") -> str:
		"""Compress a block to YAML for LLM context, extracting relevant subset."""
		import json

		try:
			data = json.loads(block_json)
		except (json.JSONDecodeError, TypeError):
			return block_json

		if isinstance(data, list):
			data = data[0] if data else {}
		if not isinstance(data, dict):
			return block_json

		if task_type == "text_only":
			texts = []
			_collect_text(data, texts)
			return "\n".join(texts)

		if task_type == "image_attrs":
			props = data.get("componentProps") or {}
			return _to_yaml({"src": props.get("image", ""), "alt": props.get("alt", "")})

		return _to_yaml([BlockCodec.compress(data)])


def _collect_text(block: dict, results: list):
	props = block.get("componentProps") or {}
	if text := props.get("text") or props.get("label") or props.get("placeholder"):
		results.append(str(text))
	for child in block.get("children", []):
		_collect_text(child, results)
	for slot in (block.get("componentSlots") or {}).values():
		if isinstance(slot, dict):
			for slot_child in (
				slot.get("slotContent", []) if isinstance(slot.get("slotContent"), list) else []
			):
				_collect_text(slot_child, results)
