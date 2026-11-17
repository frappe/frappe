"""Shared path normalization and allowed-root checks.

This is a policy boundary for path-taking built-in tools, not an operating-system
sandbox. In particular, a shell command can access anything available to the daemon
process unless it is run in a separate sandbox.
"""

from __future__ import annotations

import os
from collections.abc import Iterable


def absolute_path(path: str, *, base: str | None = None) -> str:
	"""Return an absolute addressed path without resolving symlinks."""
	candidate = path
	if base is not None and not os.path.isabs(candidate):
		candidate = os.path.join(base, candidate)
	return os.path.abspath(candidate)


def canonical_path(path: str, *, base: str | None = None) -> str:
	"""Return an absolute path with symlinks resolved for policy comparisons."""
	return os.path.realpath(absolute_path(path, base=base))


def normalize_roots(roots: Iterable[str]) -> tuple[str, ...]:
	"""Expand `~`, normalize, and de-duplicate configured roots, preserving their order.
	An unexpanded root names a directory literally called `~`, fencing off everything."""
	return tuple(dict.fromkeys(canonical_path(os.path.expanduser(root)) for root in roots))


def is_path_allowed(path: str, roots: Iterable[str], *, ignore_hidden_files: bool = False) -> bool:
	"""Whether an already-normalized path is visible under one of ``roots``."""
	for root in roots:
		try:
			if os.path.commonpath((path, root)) == root:
				relative = os.path.relpath(path, root)
				parts = () if relative == os.curdir else relative.split(os.sep)
				if not ignore_hidden_files or all(not part.startswith(".") for part in parts):
					return True
		except ValueError:
			# Different drives on Windows cannot share a common path.
			continue
	return False
