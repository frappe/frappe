# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
""" Patch Handler.

This file manages execution of manaully written patches. Patches are script
that apply changes in database schema or data to accomodate for changes in the
code.

Ways to specify patches:

1. patches.txt file specifies patches that run before doctype schema
migration. Each line represents one patch (old format).
2. patches.txt can alternatively also separate pre and post model sync
patches by using INI like file format:
	```patches.txt
	[pre_model_sync]
	app.module.patch1
	app.module.patch2


	[post_model_sync]
	app.module.patch3
	```

	When different sections are specified patches are executed in this order:
		1. Run pre_model_sync patches
		2. Reload/resync all doctype schema
		3. Run post_model_sync patches

	Hence any patch that just needs to modify data but doesn't depend on
	old schema should be added to post_model_sync section of file.

3. simple python commands can be added by starting line with `execute:`
`execute:` example: `execute:print("hello world")`
"""

import configparser
import time
from enum import Enum
from textwrap import dedent, indent

import frappe


class PatchError(Exception):
	pass


class PatchType(Enum):
	pre_model_sync = "pre_model_sync"
	post_model_sync = "post_model_sync"


def run_all(skip_failing: bool = False, patch_type: PatchType | None = None) -> None:
	"""run all pending patches"""
	executed = set(frappe.get_all("Patch Log", fields="patch", pluck="patch"))

	frappe.flags.final_patches = []

	def run_patch(patch):
		try:
			if not run_single(patchmodule=patch):
				print(patch + ": failed: STOPPED")
				raise PatchError(patch)
		except Exception:
			if not skip_failing:
				raise
			else:
				print("Failed to execute patch")

	patches = get_all_patches(patch_type=patch_type)

	for patch in patches:
		if patch and (patch not in executed):
			run_patch(patch)

	# patches to be run in the end
	for patch in frappe.flags.final_patches:
		patch = patch.replace("finally:", "")
		run_patch(patch)


def get_all_patches(patch_type: PatchType | None = None) -> list[str]:

	if patch_type and not isinstance(patch_type, PatchType):
		frappe.throw(f"Unsupported patch type specified: {patch_type}")

	patches = []
	for app in frappe.get_installed_apps():
		patches.extend(get_patches_from_app(app, patch_type=patch_type))

	return patches


def get_patches_from_app(app: str, patch_type: PatchType | None = None) -> list[str]:
	"""Get patches from an app's patches.txt

	patches.txt can be:
	        1. ini like file with section for different patch_type
	        2. plain text file with each line representing a patch.
	"""

	patches_txt = frappe.get_pymodule_path(app, "patches.txt")

	try:
		# Attempt to parse as ini file with pre/post patches
		# allow_no_value: patches are not key value pairs
		# delimiters = '\n' to avoid treating default `:` and `=` in execute as k:v delimiter
		parser = configparser.ConfigParser(allow_no_value=True, delimiters="\n")
		# preserve case
		parser.optionxform = str
		parser.read(patches_txt)

		# empty file
		if not parser.sections():
			return []

		if not patch_type:
			return [patch for patch in parser[PatchType.pre_model_sync.value]] + [
				patch for patch in parser[PatchType.post_model_sync.value]
			]

		if patch_type.value in parser.sections():
			return [patch for patch in parser[patch_type.value]]
		else:
			frappe.throw(frappe._("Patch type {} not found in patches.txt").format(patch_type))

	except configparser.MissingSectionHeaderError:
		# treat as old format with each line representing a single patch
		# backward compatbility with old patches.txt format
		if not patch_type or patch_type == PatchType.pre_model_sync:
			return frappe.get_file_items(patches_txt)

	return []


def reload_doc(args):
	import frappe.modules

	run_single(method=frappe.modules.reload_doc, methodargs=args)


def run_single(patchmodule=None, method=None, methodargs=None, force=False):
	from frappe import conf

	# don't write txt files
	conf.developer_mode = 0

	if force or method or not executed(patchmodule):
		return execute_patch(patchmodule, method, methodargs)
	else:
		return True


def execute_patch(patchmodule: str, method=None, methodargs=None):
	"""execute the patch"""
	_patch_mode(True)

	if patchmodule.startswith("execute:"):
		has_patch_file = False
		patch = patchmodule.split("execute:")[1]
		docstring = ""
	else:
		has_patch_file = True
		patch = f"{patchmodule.split(maxsplit=1)[0]}.execute"
		_patch = frappe.get_attr(patch)
		docstring = _patch.__doc__ or ""

		if docstring:
			docstring = "\n" + indent(dedent(docstring), "\t")

	print(
		f"Executing {patchmodule or methodargs} in {frappe.local.site} ({frappe.db.cur_db_name}){docstring}"
	)

	start_time = time.time()
	frappe.db.begin()
	frappe.db.auto_commit_on_many_writes = 0
	try:
		if patchmodule:
			if patchmodule.startswith("finally:"):
				# run run patch at the end
				frappe.flags.final_patches.append(patchmodule)
			else:
				if has_patch_file:
					_patch()
				else:
					exec(patch, globals())
				update_patch_log(patchmodule)

		elif method:
			method(**methodargs)

	except Exception:
		frappe.db.rollback()
		raise

	else:
		frappe.db.commit()
		end_time = time.time()
		_patch_mode(False)
		print(f"Success: Done in {round(end_time - start_time, 3)}s")

	return True


def update_patch_log(patchmodule):
	"""update patch_file in patch log"""
	frappe.get_doc({"doctype": "Patch Log", "patch": patchmodule}).insert(ignore_permissions=True)


def executed(patchmodule):
	"""return True if is executed"""
	if patchmodule.startswith("finally:"):
		# patches are saved without the finally: tag
		patchmodule = patchmodule.replace("finally:", "")
	return frappe.db.get_value("Patch Log", {"patch": patchmodule})


def _patch_mode(enable):
	"""stop/start execution till patch is run"""
	frappe.local.flags.in_patch = enable
	frappe.db.commit()


def check_session_stopped():
	"""This function is deprecated. Use maintenance_mode in site config instead."""
	if frappe.db.get_global("__session_status") == "stop":
		frappe.msgprint(frappe.db.get_global("__session_status_message"))
		raise frappe.SessionStopped("Session Stopped")
