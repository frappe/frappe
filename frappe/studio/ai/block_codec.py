import json
import re


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
		parsed = _loads_lenient(cleaned)

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

		return _to_json(BlockCodec.compress(data))


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


def _to_json(data) -> str:
	"""Compact, token-efficient JSON: no whitespace, unicode kept as-is."""
	return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _strip_fences(text: str) -> str:
	text = re.sub(r"^```(?:json|yaml)?\s*\n?", "", text.strip())
	return re.sub(r"\n?```\s*$", "", text).strip()


def _escape_inner_quotes(text: str) -> str:
	"""Escape stray double-quotes inside string values. A `"` only legitimately
	ends a string when the next non-space char is structural (`,` `}` `]` `:` or
	EOF); otherwise it is unescaped content (e.g. He said "hi") and we escape it."""
	out = []
	i, n = 0, len(text)
	in_string = False
	while i < n:
		ch = text[i]
		if not in_string:
			out.append(ch)
			if ch == '"':
				in_string = True
			i += 1
			continue
		if ch == "\\":  # keep existing escape pair intact
			out.append(ch)
			if i + 1 < n:
				out.append(text[i + 1])
				i += 2
			else:
				i += 1
			continue
		if ch == '"':
			j = i + 1
			while j < n and text[j] in " \t\r\n":
				j += 1
			nxt = text[j] if j < n else ""
			if nxt in (",", "}", "]", ":", ""):
				out.append(ch)
				in_string = False
			else:
				out.append('\\"')
			i += 1
			continue
		out.append(ch)
		i += 1
	return "".join(out)


def _close_open_structures(text: str) -> str:
	"""Best-effort completion of a truncated JSON tail: close an unterminated
	string, drop a dangling trailing comma or `"key":`, and close open brackets."""
	closers = []
	in_string = escaped = False
	for ch in text:
		if in_string:
			if escaped:
				escaped = False
			elif ch == "\\":
				escaped = True
			elif ch == '"':
				in_string = False
			continue
		if ch == '"':
			in_string = True
		elif ch == "{":
			closers.append("}")
		elif ch == "[":
			closers.append("]")
		elif ch in "}]" and closers:
			closers.pop()

	result = text + ('"' if in_string else "")
	prev = None
	while prev != result:
		prev = result
		result = result.rstrip()
		if result.endswith(","):
			result = result[:-1]
		else:
			result = re.sub(r',?\s*"(?:[^"\\]|\\.)*"\s*:$', "", result)
	return result + "".join(reversed(closers))


def _repair_json(text: str) -> str:
	text = _escape_inner_quotes(text)
	text = re.sub(r",\s*([}\]])", r"\1", text)  # trailing commas before } or ]
	return _close_open_structures(text)


def _loads_lenient(text: str):
	"""Parse JSON, tolerating the common ways LLMs emit slightly-invalid JSON:
	raw control chars (strict=False), unescaped inner quotes, trailing commas,
	and truncation. Falls back to a repair pass only when strict parsing fails."""
	try:
		return json.loads(text, strict=False)
	except json.JSONDecodeError:
		return json.loads(_repair_json(text), strict=False)
