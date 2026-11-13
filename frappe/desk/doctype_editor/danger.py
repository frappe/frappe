# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Design mode's Danger zone: acts on the whole DocType that run at once, outside the undo stack."""

import os
import re
import shutil
from pathlib import Path

import frappe
from frappe import _
from frappe.cache_manager import clear_controller_cache
from frappe.desk.doctype.form_layout.form_layout import publish_doctype_update
from frappe.desk.doctype_editor.create import remove_doctype
from frappe.desk.doctype_editor.mode import check_mode
from frappe.model.base_document import get_controller
from frappe.modules import get_doc_path, get_module_name
from frappe.utils.nestedset import NestedSet, rebuild_tree

KINDS = ("regular", "submittable", "tree", "child", "single")


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def change_kind(doctype: str, kind: str) -> None:
	check_mode(doctype, "Design")
	doc = frappe.get_doc("DocType", doctype)
	if refusal := kind_refusal(doc, kind):
		frappe.throw(refusal)
	doc.update(kind_flags(kind))
	if not doc.is_submittable:
		# Else the save refuses Submit, Cancel and Amend on a DocType that no longer submits.
		for perm in doc.permissions:
			perm.submit = perm.cancel = perm.amend = 0
	# A child table has no permissions: give it back the rule a new DocType gets.
	doc.before_insert()
	doc.save()
	if doc.is_tree:
		# Records made before the tree have no place in it yet.
		rebuild_tree(doctype)
	done(doctype)


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def rename_doctype(doctype: str, new_name: str) -> str:
	"""Renames its table and every Link and Table field that points to it; returns the new name."""
	check_mode(doctype, "Design")
	check_administrator(doctype)
	new_name = frappe.rename_doc("DocType", doctype, new_name)
	done(new_name)
	return new_name


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def delete_doctype(doctype: str) -> None:
	"""Deletes it with its records, layouts and table; custom fields that use it as a child table go too."""
	check_mode(doctype, "Design")
	check_administrator(doctype)
	remove_doctype(doctype)
	done(doctype)


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def move_doctype(doctype: str, module: str) -> None:
	"""A standard DocType's folder moves with it, so its code goes along."""
	check_mode(doctype, "Design")
	doc = frappe.get_doc("DocType", doctype)
	moved = None
	if not doc.custom:
		check_developer_mode()
		check_app_module(module)
		check_no_callers(doc)
		moved = move_folder(doc, module)
	doc.module = module
	try:
		doc.save()
	except Exception:
		if moved:
			shutil.move(moved[1], moved[0])
		raise
	done(doctype)


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def make_standard(doctype: str, module: str) -> None:
	"""One way: its save writes its files into the module's app, which then ships it."""
	check_mode(doctype, "Design")
	check_developer_mode()
	doc = frappe.get_doc("DocType", doctype)
	if not doc.custom:
		frappe.throw(_("{0} is already a standard DocType.").format(frappe.bold(doctype)))
	check_app_module(module)
	check_no_folder(module, doctype)
	doc.custom = 0
	doc.module = module
	doc.save()
	done(doctype)


def kind_refusal(doc, kind: str) -> str | None:
	if kind not in KINDS:
		return _("{0} is not a kind of DocType.").format(kind)
	if doc.issingle or kind == "single":
		return _("A Single is set when a DocType is made. Make a new DocType instead.")
	if (
		kind == "tree"
		and not doc.is_tree
		and not doc.custom
		and not issubclass(get_controller(doc.name), NestedSet)
	):
		return _(
			"{0}'s controller is not a NestedSet, so a tree would not keep its records in place."
		).format(frappe.bold(doc.name))
	if bool(doc.istable) == (kind == "child"):
		return None
	if frappe.db.count(doc.name):
		return _("{0} has records: a child table's rows need a parent record.").format(frappe.bold(doc.name))
	if doc.istable and (parent := table_parent(doc.name)):
		return _("{0} is a table in {1}.").format(frappe.bold(doc.name), frappe.bold(parent))
	return None


def table_parent(doctype: str) -> str | None:
	"""The DocType with a Table field of `doctype`, standard or custom."""
	table = {"options": doctype, "fieldtype": ("in", frappe.model.table_fields)}
	return frappe.db.get_value("DocField", table, "parent") or frappe.db.get_value(
		"Custom Field", table, "dt"
	)


def kind_flags(kind: str) -> dict:
	return {
		"istable": int(kind == "child"),
		"issingle": 0,
		"is_submittable": int(kind == "submittable"),
		"is_tree": int(kind == "tree"),
	}


def done(doctype: str) -> None:
	# Made standard or moved, it has another controller class now.
	clear_controller_cache(doctype)
	frappe.clear_cache(doctype=doctype)
	publish_doctype_update(doctype)


def check_developer_mode() -> None:
	if not frappe.conf.developer_mode:
		frappe.throw(
			_("Moving a standard DocType or making a DocType standard needs developer mode."),
			frappe.PermissionError,
		)


def check_administrator(doctype: str) -> None:
	# As v1: only Administrator renames or deletes a standard DocType.
	if not frappe.db.get_value("DocType", doctype, "custom") and frappe.session.user != "Administrator":
		frappe.throw(_("Only Administrator can rename or delete a standard DocType."), frappe.PermissionError)


def check_app_module(module: str) -> None:
	if frappe.db.get_value("Module Def", module, "custom") != 0:
		frappe.throw(_("{0} is not a module of an app.").format(frappe.bold(module)))


def move_folder(doc, module: str) -> tuple[Path, Path] | None:
	"""Moves its folder into `module`; returns (old, new) so a failed save can move it back."""
	old = Path(get_doc_path(doc.module, "doctype", doc.name))
	if not old.exists():
		return None
	new = check_no_folder(module, doc.name)
	new.parent.mkdir(parents=True, exist_ok=True)
	shutil.move(old, new)
	return old, new


CODE_SUFFIXES = {".py", ".js", ".ts", ".vue", ".html"}
SKIPPED_DIRS = {"node_modules", "dist", "__pycache__", ".git"}


def check_no_callers(doc) -> None:
	"""Refused while code outside its folder names its Python path: the move would break that import."""
	folder = Path(get_doc_path(doc.module, "doctype", doc.name))
	if not folder.exists():
		return
	path = get_module_name(doc.name, doc.module).rsplit(".", 1)[0]
	# `\b`: frappe.core.doctype.task is not frappe.core.doctype.task_note.
	named = re.compile(re.escape(path) + r"\b")
	callers = [str(file) for file in code_files() if folder not in file.parents and named.search(read(file))]
	if callers:
		frappe.throw(
			_("Code outside its folder uses {0}, so moving it would break: {1}").format(
				frappe.bold(path), ", ".join(callers[:5]) + (" …" if len(callers) > 5 else "")
			)
		)


def code_files():
	for app in frappe.get_installed_apps():
		for root, dirs, files in os.walk(frappe.get_app_path(app)):
			dirs[:] = [one for one in dirs if one not in SKIPPED_DIRS]
			yield from (Path(root, name) for name in files if Path(name).suffix in CODE_SUFFIXES)


def read(file: Path) -> str:
	try:
		return file.read_text(errors="ignore")
	except OSError:
		return ""


def check_no_folder(module: str, doctype: str) -> Path:
	"""Its folder in `module`, refused when one is there already: its old files would pair with new fields."""
	path = Path(get_doc_path(module, "doctype", doctype))
	if path.exists():
		frappe.throw(_("{0} already has a folder for {1}: {2}").format(module, doctype, path))
	return path
