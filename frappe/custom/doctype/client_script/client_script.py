# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import hashlib
import json
import os
import re
import shutil
import subprocess

import frappe
from frappe import _
from frappe.app_state import is_module_disabled
from frappe.exceptions import TemplateCompileError
from frappe.model.document import Document

RECORD_PAGE_VIEWS = ("Record",)
CLIENT_SCRIPT_CHANGED = "client_script_changed"
# `run_order` is a sort key, not a unique one; `creation` breaks the ties.
RECORD_SCRIPT_ORDER = "run_order asc, creation asc"
CLASS_LIST = ("assets", "frappe", "frontend", "classes.json")
# Only text handed to `class` is read as class names; prose is not.
CLASS_CONTEXTS = (
	re.compile(r"""\bclass(?:Name)?\s*=\s*\\?(["'])(?P<text>.*?)\\?\1""", re.S),
	re.compile(r"""\bclass(?:Name)?\s*:\s*(["'`])(?P<text>.*?)\1""", re.S),
	re.compile(r"\bclassList\.(?:add|remove|toggle|replace)\((?P<text>[^)]*)\)"),
)
CLASS_WORD = re.compile(r"[!-]?[A-Za-z](?:[\w:./%-]|\[[^\]\s]*\])*")
# The same search the compile module runs first: a script without the word never needs `node`.
TEMPLATE_WORD = re.compile(r"\btemplate\b")
# Only this file may run the compile module; frappe/tests/test_template_compiler_users.py checks it.
COMPILER = "frontend/templateCompiler"
COMPILER_ENTRY = "frontend/templateCompiler/cli.mjs"
VUE_PACKAGE = "frontend/node_modules/vue/package.json"
# A cache miss takes about 40 to 60 ms; the limit only stops a stuck `node` from holding the request.
COMPILE_TIMEOUT = 30
COMPILED_COPY = "client_script_compiled"
# An edited script leaves its old copy behind, so copies expire.
COMPILED_COPY_TTL = 7 * 24 * 60 * 60
# The hash of the compile module's key parts, by a stamp of its files: one `node` call per change.
compiler_keys: dict[tuple, str] = {}


class CompilerUnavailable(frappe.ValidationError):
	pass


class ClientScript(Document):
	_DOCTYPE_NAME = "Client Script"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		dt: DF.Link
		enabled: DF.Check
		module: DF.Link | None
		run_order: DF.Int
		script: DF.Code | None
		view: DF.Literal["List", "Form", "Record"]
	# end: auto-generated types

	def before_validate(self):
		# Package Import skips `validate` but runs this hook, so the compile check lives here.
		self.check_templates()

	def validate(self):
		self.warn_on_unknown_classes()

	def on_update(self):
		frappe.clear_cache(doctype=self.dt)
		self.notify_record_pages()

	def warn_on_unknown_classes(self):
		"""Name every class the script uses that the desk stylesheet has no rule for; never block."""
		if self.view not in RECORD_PAGE_VIEWS or not self.script:
			return
		if not (self.is_new() or self.has_value_changed("script")):
			return
		known = read_class_list()
		if known is None:
			return
		unknown = sorted(set(class_words(self.script)) - known)
		if unknown:
			frappe.msgprint(
				_(
					"These classes have no style in the desk, so they will not change how the page looks: {0}. Use classes from the desk palette."
				).format(", ".join(unknown)),
				title=_("Classes with no style"),
				indicator="orange",
			)

	def check_templates(self):
		"""Block a save whose `template:` strings do not compile; an import logs the errors and keeps the record."""
		if self.view not in RECORD_PAGE_VIEWS or not holds_template(self.script):
			return
		if not (self.is_new() or self.has_value_changed("script") or self.has_value_changed("view")):
			return
		try:
			errors = compile_templates({self.name: self.script})[self.name]["errors"]
			failure = errors and TemplateCompileError(errors_text(errors), code_errors(errors))
		except CompilerUnavailable as error:
			failure = error
		if not failure:
			return
		# Fixtures and Package Import keep the record; the first fetch skips it and reports it on the page.
		if frappe.flags.in_import or self.flags.ignore_validate:
			frappe.log_error(
				title=_("Client Script {0} does not compile").format(self.name),
				message=str(failure),
				reference_doctype=self.doctype,
				reference_name=self.name,
			)
			return
		frappe.throw(str(failure), failure, title=_("This script does not compile"))

	def on_trash(self):
		frappe.clear_cache(doctype=self.dt)
		self.notify_record_pages()

	def notify_record_pages(self):
		if self.view not in RECORD_PAGE_VIEWS:
			return
		frappe.publish_realtime(  # nosemgrep
			CLIENT_SCRIPT_CHANGED, {"dt": self.dt, "view": self.view}, after_commit=True
		)


@frappe.whitelist()
def get_client_scripts(dt: str, view: str = "Record"):
	"""Return the enabled scripts a Record page of `dt` runs, in run order."""
	validate_target(dt, view)
	frappe.has_permission(dt, "read", throw=True)

	rows = frappe.get_all(
		"Client Script",
		filters={"dt": dt, "view": view, "enabled": 1},
		fields=["name", "script", "module"],
		order_by=RECORD_SCRIPT_ORDER,
	)
	return {
		"scripts": served_scripts([row for row in rows if not is_module_disabled(row.module)]),
		"can_write": bool(frappe.has_permission("Client Script", "write")),
	}


def served_scripts(rows) -> list[dict]:
	"""Each row as the page runs it: a script with a `template:` string goes compiled, or with its error and no code."""
	sources = {row.name: row.script for row in rows if holds_template(row.script)}
	try:
		copies = {name: served_copy(result) for name, result in compile_templates(sources).items()}
	except CompilerUnavailable as error:
		copies = {name: {"script": "", "error": str(error)} for name in sources}
	return [{"name": row.name, **copies.get(row.name, {"script": row.script or ""})} for row in rows]


def served_copy(result: dict) -> dict:
	if result["errors"]:
		return {"script": "", "error": error_text(result["errors"][0])}
	return {"script": result["code"]}


@frappe.whitelist(methods=["POST"])
def reorder(dt: str, view: str, names: list[str]) -> None:
	"""Renumber `names` densely from 1 in the given order, in one transaction."""
	validate_target(dt, view)
	if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
		frappe.throw(_("Scripts must be a list of names"))
	frappe.has_permission("Client Script", "write", throw=True)
	reject_foreign_names(dt, view, names)

	# `modified` stays put: the editor's lock on it means "this script's text changed".
	positions = {name: {"run_order": position} for position, name in enumerate(names, start=1)}
	frappe.db.bulk_update("Client Script", positions, update_modified=False)

	frappe.publish_realtime(CLIENT_SCRIPT_CHANGED, {"dt": dt, "view": view}, after_commit=True)  # nosemgrep


def validate_target(dt: str, view: str) -> None:
	# A non-str `dt` would reach `get_all` as a filter operator and read every doctype's scripts.
	if not isinstance(dt, str):
		frappe.throw(_("Document Type must be a name"))
	if view not in RECORD_PAGE_VIEWS:
		frappe.throw(_("Client Scripts for the {0} view are not served to a record page").format(view))


def reject_foreign_names(dt: str, view: str, names: list[str]) -> None:
	"""Refuse a duplicate or a name outside this doctype's list; a missing name is tolerated."""
	if len(set(names)) != len(names):
		frappe.throw(_("A script cannot appear twice in the run order"))

	known = set(frappe.get_all("Client Script", filters={"dt": dt, "view": view}, pluck="name"))
	unknown = sorted(set(names) - known)
	if unknown:
		frappe.throw(_("Not Client Scripts of {0}: {1}").format(dt, ", ".join(unknown)))


def read_class_list() -> set[str] | None:
	"""The classes the desk build generated, or None when no build has written a readable list."""
	try:
		with open(class_list_path()) as file:  # nosemgrep
			names = json.load(file)
	except (OSError, ValueError):
		return None
	if not isinstance(names, list):
		return None
	return {name for name in names if isinstance(name, str)}


def class_list_path() -> str:
	return os.path.join(frappe.local.sites_path, *CLASS_LIST)


def class_words(script: str) -> list[str]:
	"""Utility-shaped words (a hyphen or a variant colon) where the script names classes."""
	words = []
	for context in CLASS_CONTEXTS:
		for match in context.finditer(script):
			words += [w for w in CLASS_WORD.findall(match.group("text")) if "-" in w or ":" in w]
	return words


def holds_template(script: str | None) -> bool:
	return bool(script and TEMPLATE_WORD.search(script))


def compile_templates(scripts: dict[str, str]) -> dict[str, dict]:
	"""Each script's `{code, errors}` by name: from Redis, or from one `node` call for all the misses."""
	if not scripts:
		return {}
	compiler = compiler_key()
	keys = {name: compiled_copy_key(compiler, script) for name, script in scripts.items()}
	results = {name: frappe.cache.get_value(key) for name, key in keys.items()}
	missing = [{"name": name, "script": scripts[name]} for name, result in results.items() if result is None]
	if not missing:
		return results
	for row in run_compiler(stdin=json.dumps(missing)):
		result = results[row["name"]] = {"code": row["code"], "errors": row["errors"]}
		# A failed compile is cached too, so a broken script costs one `node` call, not one per page load.
		frappe.cache.set_value(keys[row["name"]], result, expires_in_sec=COMPILED_COPY_TTL)
	return results


def compiled_copy_key(compiler: str, script: str) -> str:
	# No doctype, record or user: the copy is right for this text even if the save rolls back.
	return f"{COMPILED_COPY}:{compiler}:{hashlib.sha256(script.encode()).hexdigest()}"


def compiler_key() -> str:
	"""A hash of the compile module's key parts: the compiler, Vue's version, the build, options and names."""
	stamp = compiler_stamp()
	if stamp not in compiler_keys:
		parts = json.dumps(run_compiler("--key-parts"), sort_keys=True)
		compiler_keys.clear()
		compiler_keys[stamp] = hashlib.sha256(parts.encode()).hexdigest()[:16]
	return compiler_keys[stamp]


def compiler_stamp() -> tuple:
	"""The time and size of each compile module file and of Vue's version file; the key parts move only with them."""
	try:
		paths = sorted(entry.path for entry in os.scandir(compiler_path(COMPILER)) if entry.is_file())
		paths.append(compiler_path(VUE_PACKAGE))
		return tuple((path, os.stat(path).st_mtime_ns, os.stat(path).st_size) for path in paths)
	except FileNotFoundError:
		raise CompilerUnavailable(_("The template compiler is not installed. Run bench build to install it."))


def run_compiler(*args: str, stdin: str = ""):
	"""The parsed output of the compile module's server entry. Author code never runs, even in a reader's fetch."""
	node = shutil.which("node")
	if not node:
		raise CompilerUnavailable(
			_("Node.js is not installed on this server, so a script with a template: string cannot compile.")
		)
	# The flag makes any `new Function` in the compiler fail the compile instead of running.
	command = [node, "--disallow-code-generation-from-strings", compiler_path(COMPILER_ENTRY), *args]
	try:
		process = subprocess.run(
			command, input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=COMPILE_TIMEOUT
		)
	except subprocess.TimeoutExpired:
		raise CompilerUnavailable(
			_("The template compiler did not finish in {0} seconds.").format(COMPILE_TIMEOUT)
		) from None
	if process.returncode:
		raise CompilerUnavailable(_("The template compiler failed: {0}").format(error_line(process.stderr)))
	return json.loads(process.stdout)


def compiler_path(path: str) -> str:
	return os.path.join(frappe.get_app_source_path("frappe"), path)


def error_line(stderr: str) -> str:
	"""Node's own error line, not the stack or the version line that follow it."""
	lines = [line.strip() for line in stderr.splitlines() if line.strip()]
	return next((line for line in lines if re.match(r"\w*Error\b", line)), lines[-1] if lines else "")


def code_errors(errors: list[dict]) -> list[dict]:
	return [{"field": "script", **error} for error in errors]


def errors_text(errors: list[dict]) -> str:
	return "\n".join(error_text(error) for error in errors)


def error_text(error: dict) -> str:
	return _("Line {0}, column {1}: {2}").format(error["line"], error["column"], error["message"])
