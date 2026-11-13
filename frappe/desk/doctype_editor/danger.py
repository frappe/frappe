# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Design mode's Danger zone: acts on the whole DocType that run at once, outside the undo stack."""

import shutil
from pathlib import Path

import frappe
from frappe import _
from frappe.cache_manager import clear_controller_cache
from frappe.desk.doctype.form_layout.form_layout import publish_doctype_update
from frappe.desk.doctype_editor.create import remove_doctype
from frappe.desk.doctype_editor.mode import check_mode
from frappe.modules import get_doc_path
from frappe.utils.nestedset import rebuild_tree

KINDS = ("regular", "submittable", "tree", "child", "single")


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def change_kind(doctype: str, kind: str) -> None:
	check_mode(doctype, "Design")
	doc = frappe.get_doc("DocType", doctype)
	if refusal := kind_refusal(doc, kind):
		frappe.throw(refusal)
	doc.update(kind_flags(kind))
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
	new_name = frappe.rename_doc("DocType", doctype, new_name)
	done(new_name)
	return new_name


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def delete_doctype(doctype: str) -> None:
	"""Deletes it with its records, layouts and table; custom fields that use it as a child table go too."""
	check_mode(doctype, "Design")
	remove_doctype(doctype, force=False)
	done(doctype)


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def move_doctype(doctype: str, module: str) -> None:
	"""A standard DocType's folder moves with it, so its code goes along."""
	check_mode(doctype, "Design")
	check_developer_mode()
	doc = frappe.get_doc("DocType", doctype)
	if not doc.custom:
		check_app_module(module)
		move_folder(doc, module)
	doc.module = module
	doc.save()
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
	doc.custom = 0
	doc.module = module
	doc.save()
	done(doctype)


def kind_refusal(doc, kind: str) -> str | None:
	if kind not in KINDS:
		return _("{0} is not a kind of DocType.").format(kind)
	if doc.issingle or kind == "single":
		return _("A Single is set when a DocType is made. Make a new DocType instead.")
	if bool(doc.istable) != (kind == "child") and frappe.db.count(doc.name):
		return _("{0} has records: a child table's rows need a parent record.").format(frappe.bold(doc.name))
	return None


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
		frappe.throw(_("Moving a DocType or making it standard needs developer mode."), frappe.PermissionError)


def check_app_module(module: str) -> None:
	if frappe.db.get_value("Module Def", module, "custom") != 0:
		frappe.throw(_("{0} is not a module of an app.").format(frappe.bold(module)))


def move_folder(doc, module: str) -> None:
	old = Path(get_doc_path(doc.module, "doctype", doc.name))
	if not old.exists():
		return
	new = Path(get_doc_path(module, "doctype", doc.name))
	new.parent.mkdir(parents=True, exist_ok=True)
	shutil.move(old, new)
