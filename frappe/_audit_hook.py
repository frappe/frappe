import os
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
	trusted_roots = (
		os.path.join(bench_path, "apps"),
		os.path.join(bench_path, "logs"),
		os.path.realpath(sys.prefix),
		os.path.realpath(sys.base_prefix),
	)

	untrusted_roots = (
		os.path.realpath(tempfile.gettempdir()),
		"/tmp",
	)
	sys.addaudithook(frappe_security_audit_hook)


def start() -> None:
	"""Scope the hook to the current site. Called from `before_request` and `before_job`."""
	if mode != AuditHookMode.OFF and getattr(frappe.local, "site_path", None):
		frappe.local.audit_roots = {
			"trusted": trusted_roots,
			"untrusted": (*untrusted_roots, os.path.realpath(frappe.local.site_path)),
		}


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
		frappe.logger("security").warning(
			f"Unsafe {event} on {path!r} (resolved to {os.path.realpath(path)!r}), "
			f"mode={mode.value}, site={getattr(frappe.local, 'site', None)}"
		)
	finally:
		_recursion_guard.is_active = False

	if mode == AuditHookMode.BLOCK:
		raise PermissionError(f"Path blocked by Frappe audit hook: {path}")
