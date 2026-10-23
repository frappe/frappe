"""Workspace file access for the web UI's explorer and editor, with the
viewer's caps mapped to HTTP errors."""

from __future__ import annotations

import os
import re

from fastapi import HTTPException

from flow_harness.path_policy import absolute_path, canonical_path, is_path_allowed

# viewer payload cap; anything bigger is not a file to render in a chat UI
MAX_FILE_VIEW_BYTES = 2 * 1024 * 1024

# file-name search: skip dependency/VCS trees, cap results, and bound the walk
# itself so a huge un-pruned tree cannot pin a thread per keystroke
SEARCH_SKIP_DIRS = {"node_modules", "__pycache__", "venv", "dist", "build", "target"}
MAX_SEARCH_RESULTS = 200
MAX_SEARCH_SCAN = 20_000


def resolve_allowed_path(cwd: str, path: str, allowed_roots) -> str:
	"""A cwd-relative client path, refused outside the allowed roots."""
	full_path = absolute_path(path, base=cwd)
	if allowed_roots and not is_path_allowed(canonical_path(full_path), allowed_roots):
		raise HTTPException(status_code=403, detail="path is outside the allowed roots")
	return full_path


def read_text_file(full_path: str, *, strip_bom: bool = False) -> str:
	"""Workspace file bytes as text, with the viewer's caps mapped to HTTP errors."""
	data = read_file_bytes(full_path, MAX_FILE_VIEW_BYTES)
	try:
		text = data.decode("utf-8")
	except UnicodeDecodeError:
		raise HTTPException(status_code=415, detail="not a text file") from None
	# BOM-stripped callers diff line one cleanly (the edit tool records BOM-less diffs)
	return text.removeprefix("\ufeff") if strip_bom else text


def read_file_bytes(full_path: str, max_bytes: int, *, purpose: str = "display") -> bytes:
	"""Raw file bytes under a size cap, with the workspace routes' error mapping."""
	if not os.path.isfile(full_path):
		raise HTTPException(status_code=404, detail="file not found")
	if os.path.getsize(full_path) > max_bytes:
		raise HTTPException(status_code=413, detail=f"file too large to {purpose}")
	try:
		with open(full_path, "rb") as f:
			return f.read()
	except PermissionError:
		raise HTTPException(status_code=403, detail="file is not readable") from None


def read_file_head(full_path: str, size: int) -> bytes:
	"""A file's first `size` bytes, with the workspace routes' error mapping."""
	try:
		with open(full_path, "rb") as f:
			return f.read(size)
	except PermissionError:
		raise HTTPException(status_code=403, detail="file is not readable") from None


def save_text_file(full_path: str, content: str) -> None:
	"""Write the viewer's edits, creating parent directories like the write tool does."""
	try:
		os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
		with open(full_path, "w", encoding="utf-8", newline="") as f:
			f.write(content)
	except PermissionError:
		raise HTTPException(status_code=403, detail="file is not writable") from None
	except IsADirectoryError:
		raise HTTPException(status_code=400, detail="path is a directory") from None


def list_directory(full_path: str) -> list[dict]:
	"""One directory level for the file explorer, errors mapped to HTTP."""
	try:
		with os.scandir(full_path) as it:
			entries = [{"name": e.name, "type": "dir" if e.is_dir() else "file"} for e in it]
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail="directory not found") from None
	except NotADirectoryError:
		raise HTTPException(status_code=400, detail="not a directory") from None
	except PermissionError:
		raise HTTPException(status_code=403, detail="directory is not readable") from None
	entries.sort(key=lambda e: (e["type"] != "dir", e["name"].lower()))
	return entries


def search_tree(root: str, needle: str) -> tuple[list[str], bool]:
	"""Files and folders (ending in "/") whose own name holds the needle's last slash- or
	space-separated term, after any earlier ones in order along the path — "src/agent"
	finds src/flow_harness/agent/, so a partial path skips levels. Hidden and dependency
	directories are pruned."""
	terms = [term for term in re.split(r"[\s/]+", needle) if term]
	matches: list[str] = []
	scanned = 0
	for dirpath, dirnames, filenames in os.walk(root):
		# directories count too, so file-sparse deep trees still hit the cap
		scanned += 1
		if scanned >= MAX_SEARCH_SCAN:
			return matches, True
		dirnames[:] = sorted(
			(d for d in dirnames if not d.startswith(".") and d not in SEARCH_SKIP_DIRS),
			key=str.lower,
		)
		# a folder is listed before what it holds, and counted when it is walked
		folders = [(name, "/") for name in dirnames]
		files = [(name, "") for name in sorted(filenames, key=str.lower)]
		for name, slash in folders + files:
			scanned += not slash
			rel = os.path.relpath(os.path.join(dirpath, name), root)
			if _path_matches(rel.lower(), terms, len(rel) - len(name)):
				matches.append(rel + slash)
				if len(matches) >= MAX_SEARCH_RESULTS:
					return matches, True
			if scanned >= MAX_SEARCH_SCAN:
				return matches, True
	return matches, False


def _path_matches(path: str, terms: list[str], name_start: int) -> bool:
	position = 0
	for i, term in enumerate(terms):
		# the last term lands in the entry's own name
		start = max(position, name_start) if i == len(terms) - 1 else position
		position = path.find(term, start)
		if position == -1:
			return False
		position += len(term)
	return True
