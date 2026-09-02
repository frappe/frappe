"""Workspace file access for the web UI's explorer and editor, with the
viewer's caps mapped to HTTP errors."""

from __future__ import annotations

import os

from fastapi import HTTPException

# viewer payload cap; anything bigger is not a file to render in a chat UI
MAX_FILE_VIEW_BYTES = 2 * 1024 * 1024

# file-name search: skip dependency/VCS trees, cap results, and bound the walk
# itself so a huge un-pruned tree cannot pin a thread per keystroke
SEARCH_SKIP_DIRS = {"node_modules", "__pycache__", "venv", "dist", "build", "target"}
MAX_SEARCH_RESULTS = 200
MAX_SEARCH_SCAN = 20_000


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
	"""File-name matches under root; hidden and dependency directories are pruned."""
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
		for name in sorted(filenames, key=str.lower):
			scanned += 1
			if needle in name.lower():
				matches.append(os.path.relpath(os.path.join(dirpath, name), root))
				if len(matches) >= MAX_SEARCH_RESULTS:
					return matches, True
			if scanned >= MAX_SEARCH_SCAN:
				return matches, True
	return matches, False
