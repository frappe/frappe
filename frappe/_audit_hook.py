"""PEP 578 Audit Hook for Frappe Security.

Provides filesystem access monitoring and path traversal prevention.
"""

import logging
import mimetypes
import os
import shutil
import ssl
import sys
import tempfile
import threading
import zoneinfo
from enum import Enum

import frappe

WATCHED_EVENTS = frozenset(
	(
		"open",
		"os.mkdir",
		"os.rename",
		"os.remove",
		"os.rmdir",
		"os.symlink",
		"os.link",
		"os.truncate",
		"shutil.rmtree",
	)
)

TWO_PATH_EVENTS = frozenset(("os.rename", "os.symlink", "os.link"))

WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC

MAX_REPORTED = 1024


class AuditHookMode(Enum):
	OFF = "off"
	LOG = "log"
	BLOCK = "block"


mode = AuditHookMode.OFF
read_roots: tuple[str, ...] = ()
write_roots: tuple[str, ...] = ()
config_owners: frozenset[str] = frozenset()

_recursion_guard = threading.local()
_reported: set[tuple[str, str]] = set()


def setup_audit_hook() -> None:
	"""Register the hook unless `FRAPPE_AUDIT_HOOK_MODE` is "off".

	Audit hooks can not be removed once added, so OFF installs nothing at all instead of
	installing a hook that returns early on every file access in the process.
	"""
	global mode, read_roots, write_roots, config_owners

	try:
		requested_mode = AuditHookMode(os.environ.get("FRAPPE_AUDIT_HOOK_MODE", "log").strip().lower())
	except ValueError:
		return

	if requested_mode == AuditHookMode.OFF:
		return

	from frappe.utils import get_bench_path

	bench_path = os.path.realpath(get_bench_path())
	mode = requested_mode

	read_paths = [
		os.path.join(bench_path, "apps"),
		sys.prefix,
		sys.base_prefix,
		"/dev/urandom",
		"/dev/zero",
		"/etc/fonts",
		"/usr/share/fonts",
		*zoneinfo.TZPATH,
	]

	verify = ssl.get_default_verify_paths()
	read_paths += (verify.cafile, verify.capath, verify.openssl_cafile, verify.openssl_capath)

	read_paths += (shutil.which(binary) for binary in ("wkhtmltopdf", "chromium", "node", "yarn"))

	read_paths += (path for path in mimetypes.knownfiles if os.path.isfile(path))

	read_roots = _resolve(read_paths)
	write_roots = _resolve(
		(
			tempfile.gettempdir(),
			"/tmp",
			"/var/tmp",
			os.path.join(bench_path, "logs"),
			"/dev/null",
		)
	)

	frappe_dir = os.path.dirname(frappe.__file__)
	config_owners = frozenset(
		(
			os.path.join(frappe_dir, "config.py"),
			os.path.join(frappe_dir, "installer.py"),
			os.path.join(frappe_dir, "utils", "backups.py"),
		)
	)

	sys.addaudithook(frappe_security_audit_hook)


def _resolve(paths) -> tuple[str, ...]:
	return tuple(dict.fromkeys(os.path.realpath(path) for path in paths if path))


def start() -> None:
	"""Scope the hook to the current site. Called from `before_request` and `before_job`."""
	if mode == AuditHookMode.OFF or not getattr(frappe.local, "site_path", None):
		return

	sites_path = os.path.realpath(frappe.local.sites_path)
	site_path = os.path.realpath(frappe.local.site_path)

	read = (
		*read_roots,
		os.path.join(sites_path, "assets"),
		os.path.join(sites_path, "apps.txt"),
		os.path.join(sites_path, "apps.json"),
	)

	write = [*write_roots, site_path]
	if backup_path := frappe.local.conf.get("backup_path"):
		write.append(os.path.realpath(os.path.join(site_path, backup_path)))

	config_files = frozenset(
		(
			os.path.realpath(os.path.join(site_path, "site_config.json")),
			os.path.realpath(os.path.join(sites_path, "common_site_config.json")),
		)
	)

	frappe.local.audit_roots = {"read": read, "write": tuple(write), "config": config_files}


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

	if event == "open":
		mode_arg, flags = args[1], args[2]
		is_write = bool(flags & WRITE_FLAGS) or bool(mode_arg and any(c in mode_arg for c in "wxa+"))
		paths = args[:1]
	else:
		is_write = True
		paths = args[:2] if event in TWO_PATH_EVENTS else args[:1]

	for arg in paths:
		if not isinstance(arg, str | bytes | os.PathLike):
			continue

		path = os.fsdecode(arg)

		if not os.path.isabs(path) and _is_rmtree_internal(sys._getframe(1)):
			continue

		if not is_allowed_path(path, roots, is_write):
			handle_violation(event, path)


def _is_rmtree_internal(frame) -> bool:
	return frame.f_code.co_filename == shutil.__file__ and frame.f_code.co_name.startswith("_rmtree")


def is_allowed_path(path: str, roots: dict, is_write: bool) -> bool:
	"""Resolve the path and check it against the roots for this kind of access."""
	# compile() and ast.parse() use synthetic names like <unknown>, <serverscript> and
	# <safe_eval>, which linecache then tries to open. Not filesystem paths.
	if path.startswith("<") and path.endswith(">"):
		return True

	resolved = os.path.realpath(path)

	if resolved in roots["config"]:
		return called_from_config_owner()

	if is_inside(resolved, roots["write"]):
		return True

	return not is_write and is_inside(resolved, roots["read"])


def called_from_config_owner() -> bool:
	"""Whether one of `config_owners` is the one opening the file.

	open() reaches them through helpers like get_file_json, so walk a few frames up instead of
	indexing one. Bounded, so an unrelated frame deep in the stack can't vouch for the call.
	"""
	frame = sys._getframe(1)
	for _ in range(8):
		if frame is None:
			return False
		if frame.f_code.co_filename in config_owners:
			return True
		frame = frame.f_back
	return False


def is_inside(path: str, roots: tuple[str, ...]) -> bool:
	"""Check whether the path is the root itself or anywhere in its subtree."""
	return any(path == root or path.startswith(root + os.sep) for root in roots)


def handle_violation(event: str, path: str) -> None:
	key = (event, path)
	if key not in _reported:
		_recursion_guard.is_active = True
		try:
			if len(_reported) >= MAX_REPORTED:
				_reported.clear()
			_reported.add(key)

			logger = frappe.logger("security")
			if logger.level > logging.WARNING:
				logger.setLevel(logging.WARNING)

			logger.warning(
				f"Unsafe {event} on {path!r} (resolved to {os.path.realpath(path)!r}), "
				f"mode={mode.value}, site={getattr(frappe.local, 'site', None)}"
			)
		except OSError:
			pass
		finally:
			_recursion_guard.is_active = False

	if mode == AuditHookMode.BLOCK:
		raise PermissionError(f"Path blocked by Frappe audit hook: {path}")
