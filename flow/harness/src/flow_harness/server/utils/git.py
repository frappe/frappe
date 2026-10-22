"""Read-only git queries backing the web UI's uncommitted-changes views."""

from __future__ import annotations

import os
import subprocess

from fastapi import HTTPException

from flow_harness.path_policy import canonical_path, is_path_allowed
from flow_harness.server.utils.workspace import MAX_FILE_VIEW_BYTES


def git_changes(cwd: str, allowed_roots: tuple[str, ...]) -> dict:
	"""Working-tree changes vs HEAD (staged, unstaged, and untracked), whole repo.
	`root` is None outside a repository; files outside the allowed roots are dropped."""
	top = git_output(cwd, "rev-parse", "--show-toplevel")
	if top is None:
		return {"root": None, "files": []}
	root = top.decode("utf-8", "replace").strip()
	counts: dict[str, tuple[int, int]] = {}
	# no HEAD yet (fresh repo): every file counts like an untracked one below
	if git_output(root, "rev-parse", "--verify", "--quiet", "HEAD") is not None:
		numstat = git_output(root, "diff", "--numstat", "--no-renames", "-z", "HEAD") or b""
		for record in numstat.decode("utf-8", "replace").split("\0"):
			fields = record.split("\t")
			if len(fields) != 3:
				continue
			added, removed, rel = fields
			counts[rel] = (
				int(added) if added.isdigit() else 0,  # "-" marks a binary file
				int(removed) if removed.isdigit() else 0,
			)
	status = git_output(root, "status", "--porcelain", "--no-renames", "--untracked-files=all", "-z") or b""
	files = []
	seen: set[str] = set()
	for record in status.decode("utf-8", "replace").split("\0"):
		if len(record) < 4:
			continue
		rel = record[3:]
		# an index/worktree split (e.g. `git rm --cached`) lists one path twice
		if rel in seen:
			continue
		seen.add(rel)
		full_path = os.path.join(root, rel)
		if allowed_roots and not is_path_allowed(canonical_path(full_path), allowed_roots):
			continue
		added, removed = counts[rel] if rel in counts else (_count_lines(full_path), 0)
		files.append({"path": full_path, "added": added, "removed": removed})
	files.sort(key=lambda f: f["path"])
	return {"root": root, "files": files}


def git_branch(cwd: str) -> dict:
	"""The branch checked out, None on a detached HEAD or outside a repository, and whether
	the folder is a linked worktree."""
	top = git_output(cwd, "rev-parse", "--show-toplevel")
	if top is None:
		return {"branch": None, "worktree": False}
	root = top.decode("utf-8", "replace").strip()
	head = git_output(root, "symbolic-ref", "--short", "-q", "HEAD")
	# a linked worktree has a git dir of its own beside the repository's shared one
	dirs = git_output(root, "rev-parse", "--git-dir", "--git-common-dir") or b""
	paths = {os.path.realpath(os.path.join(root, d)) for d in dirs.decode("utf-8", "replace").splitlines()}
	return {"branch": head.decode("utf-8", "replace").strip() if head else None, "worktree": len(paths) == 2}


def git_head_text(root: str, rel: str) -> str:
	"""The file's HEAD content; empty when git has no blob for it (untracked, new repo)."""
	blob = git_output(root, "show", f"HEAD:{rel}")
	if blob is None:
		return ""
	if len(blob) > MAX_FILE_VIEW_BYTES:
		raise HTTPException(status_code=413, detail="file too large to display")
	try:
		return blob.decode("utf-8")
	except UnicodeDecodeError:
		raise HTTPException(status_code=415, detail="not a text file") from None


def git_output(cwd: str, *args: str) -> bytes | None:
	try:
		completed = subprocess.run(["git", "-C", cwd, *args], capture_output=True)
	except OSError:
		return None
	return completed.stdout if completed.returncode == 0 else None


def _count_lines(full_path: str) -> int:
	"""Line count of an untracked text file, 0 for anything unreadable/binary/huge."""
	try:
		if os.path.getsize(full_path) > MAX_FILE_VIEW_BYTES:
			return 0
		with open(full_path, "rb") as f:
			data = f.read()
	except OSError:
		return 0
	if b"\0" in data:
		return 0
	return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
