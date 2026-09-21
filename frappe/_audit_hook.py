"""PEP 578 Audit Hook for Frappe Security.

Provides filesystem access monitoring and path traversal prevention.
"""

import logging
import mimetypes
import os
import shutil
import sys
import tempfile
import threading
from enum import Enum

import frappe

_recursion_guard = threading.local()

WATCHED_EVENTS = frozenset(
	("open", "os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.symlink", "os.link", "os.truncate")
)


class AuditHookMode(Enum):
	OFF = "off"
	LOG = "log"
	BLOCK = "block"


trusted_roots: tuple[str, ...] = ()
untrusted_roots: tuple[str, ...] = ()


mode = AuditHookMode.OFF


def setup_audit_hook() -> None:
	"""Register the hook if `FRAPPE_AUDIT_HOOK_MODE` asks for it.

	Audit hooks can not be removed once added, so OFF installs nothing at all instead of
	installing a hook that returns early on every file access in the process.
	"""
	global mode, trusted_roots, untrusted_roots

	try:
		requested_mode = AuditHookMode(os.environ.get("FRAPPE_AUDIT_HOOK_MODE", "off").strip().lower())
	except ValueError:
		return

	if requested_mode == AuditHookMode.OFF:
		return

	from frappe.utils import get_bench_path

	bench_path = os.path.realpath(get_bench_path())
	mode = requested_mode
	trusted_paths = [
		os.path.join(bench_path, "apps"),
		os.path.join(bench_path, "logs"),
		os.path.realpath(sys.prefix),
		os.path.realpath(sys.base_prefix),
		os.path.realpath("/dev/null"),
		os.path.realpath("/dev/urandom"),
		os.path.realpath("/dev/zero"),
	]

	for binary in ("wkhtmltopdf", "chromium", "node", "yarn"):
		if bin_path := shutil.which(binary):
			trusted_paths.append(os.path.realpath(bin_path))

	for mime_path in getattr(mimetypes, "knownfiles", []):
		if os.path.isfile(mime_path):
			trusted_paths.append(os.path.realpath(mime_path))

	trusted_roots = tuple(trusted_paths)

	untrusted_roots = (
		os.path.realpath(tempfile.gettempdir()),
		os.path.realpath("/tmp"),
		os.path.realpath("/var/tmp"),
	)
	sys.addaudithook(frappe_security_audit_hook)


def start() -> None:
	"""Scope the hook to the current site. Called from `before_request` and `before_job`."""

	if mode == AuditHookMode.OFF or not getattr(frappe.local, "site_path", None):
		return
	# Bench-level files shared by every site. Enumerated rather than allowing all of
	# sites/, which would let one site read another's site_config.json.
	sites_path = os.path.realpath(frappe.local.sites_path)
	trusted = (
		*trusted_roots,
		os.path.join(sites_path, "assets"),
		os.path.join(sites_path, "common_site_config.json"),
		os.path.join(sites_path, "apps.txt"),
		os.path.join(sites_path, "apps.json"),
	)
	site_path = os.path.realpath(frappe.get_site_path())
	untrusted = [*untrusted_roots, site_path]

	if backup_path := frappe.local.conf.get("backup_path"):
		untrusted.append(os.path.realpath(os.path.join(site_path, backup_path)))

	frappe.local.audit_roots = {"trusted": trusted, "untrusted": tuple(untrusted)}


def stop() -> None:
	frappe.local.audit_roots = None


def frappe_security_audit_hook(event: str, args: tuple) -> None:
	if event not in WATCHED_EVENTS:
		return

	if getattr(_recursion_guard, "is_active", False):
		return

	roots = getattr(frappe.local, "audit_roots", None)
	if roots is None:
		return

	paths = args[:2] if event in ("os.rename", "os.symlink", "os.link") else args[:1]

	for arg in paths:
		if not isinstance(arg, str | bytes | os.PathLike):
			continue

		path = os.fsdecode(arg)
		if not is_allowed_path(path, roots):
			handle_violation(event, path)


def is_allowed_path(path: str, roots: dict[str, tuple[str, ...]]) -> bool:
	"""Resolve the path only when the cheap lexical check is inconclusive.

	Almost every access is an already normalised absolute path (the interpreter importing
	modules, mostly) and never reaches `realpath`, which costs a syscall per component.
	"""

	# compile() and ast.parse() use synthetic names like <unknown>, <serverscript> and
	# <safe_eval>, which linecache then tries to open. Not filesystem paths.
	if path.startswith("<") and path.endswith(">"):
		return True

	# Code directories are not writable through the web, so a symlink planted there already
	# implies code execution. Skipping realpath() keeps the hot path free of syscalls
	if path.startswith(os.sep) and ".." not in path:
		if is_inside(path, roots["trusted"]):
			return True

	resolved = os.path.realpath(path)
	return is_inside(resolved, roots["trusted"]) or is_inside(resolved, roots["untrusted"])


def is_inside(path: str, roots: tuple[str, ...]) -> bool:
	"""Check whether the path is the root itself or anywhere in its subtree."""
	return any(path == root or path.startswith(root + os.sep) for root in roots)


def handle_violation(event: str, path: str) -> None:
	_recursion_guard.is_active = True
	try:
		logger = frappe.logger("security")
		if logger.level > logging.WARNING:
			logger.setLevel(logging.WARNING)

		logger.warning(
			f"Unsafe {event} on {path!r} (resolved to {os.path.realpath(path)!r}), "
			f"mode={mode.value}, site={getattr(frappe.local, 'site', None)}"
		)
	finally:
		_recursion_guard.is_active = False

	if mode == AuditHookMode.BLOCK:
		raise PermissionError(f"Path blocked by Frappe audit hook: {path}")
