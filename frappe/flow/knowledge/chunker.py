# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Character-based fixed-size chunking with overlap.

Sizes are character counts. Chunks break on whitespace where possible so a
word is not split across two chunks; text with no whitespace falls back to a
hard split at chunk_size.
"""

from __future__ import annotations


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
	if chunk_size < 1:
		raise ValueError("chunk_size must be >= 1")
	if overlap < 0 or overlap >= chunk_size:
		raise ValueError("overlap must be in [0, chunk_size)")

	text = text.strip()
	if not text:
		return []
	if len(text) <= chunk_size:
		return [text]

	chunks: list[str] = []
	start = 0
	length = len(text)
	while start < length:
		end = min(start + chunk_size, length)
		if end < length:
			boundary = max(text.rfind(" ", start, end), text.rfind("\n", start, end))
			if boundary > start:
				end = boundary

		chunk = text[start:end].strip()
		if chunk:
			chunks.append(chunk)
		if end >= length:
			break
		# Step back by overlap, but always advance to avoid an infinite loop.
		start = max(end - overlap, start + 1)

	return chunks
