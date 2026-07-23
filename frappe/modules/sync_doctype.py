# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Sync a hand-edited DocType JSON file through the validated document lifecycle.

Unlike `frappe.reload_doc` / `import_file` (which intentionally skip validation for
migrations), this path applies the file's contents onto the DocType document and calls
`save()`, so validation, schema sync (`updatedb`), controller stubs and type annotations
all run. The save re-exports the JSON, renormalizing whatever the editor got wrong.
"""

import os
from pathlib import Path

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.modules.utils import get_doc_path, scrub


class DocTypeSyncError(frappe.ValidationError):
	pass


# Framework-managed keys: always taken from the database, never from the edited file.
IGNORED_KEYS = (
	"modified",
	"modified_by",
	"creation",
	"owner",
	"docstatus",
	"idx",
	"migration_hash",
	"__islocal",
	"__unsaved",
)


def sync_doctype_from_file(target: str) -> dict:
	"""Push an edited DocType JSON file through the full validated save pipeline.

	:param target: DocType name or path to the exported ``.json`` file.
	:return: dict with ``doctype``, ``path``, ``renormalized`` and ``warnings``.
	"""
	if not frappe.conf.developer_mode:
		frappe.throw(
			_("This command requires developer_mode. Enable it with: bench set-config developer_mode 1"),
			DocTypeSyncError,
		)

	path, data = _resolve_target(target)

	name = data.get("name")
	if data.get("doctype") != "DocType" or not name:
		frappe.throw(
			_("{0} is not a DocType definition (expected keys 'doctype': 'DocType' and 'name')").format(path),
			DocTypeSyncError,
		)

	if data.get("custom"):
		frappe.throw(
			_(
				"{0} is marked custom; custom DocTypes live in the database and are not synced from files"
			).format(name),
			DocTypeSyncError,
		)

	module = data.get("module")
	if not module:
		frappe.throw(_("DocType {0} has no 'module' set in the JSON file").format(name), DocTypeSyncError)

	expected_path = _expected_export_path(module, name)
	if os.path.realpath(path) != os.path.realpath(expected_path):
		frappe.throw(
			_(
				"File is at {0} but DocType {1} (module {2}) exports to {3}. "
				"Move the file to the canonical location, or fix the 'module'/'name' keys. "
				"To customize another app's DocType use Custom Fields / Property Setters instead."
			).format(path, name, module, expected_path),
			DocTypeSyncError,
		)

	exists = frappe.db.exists("DocType", name)
	warnings = []

	if exists:
		warnings.extend(_detect_possible_renames(name, data))

	original_text = Path(path).read_text()

	doc_data = {key: value for key, value in data.items() if key not in IGNORED_KEYS}
	doc = frappe.get_doc(doc_data)

	if exists:
		# the exported JSON omits falsy values; fill defaults for missing keys so an
		# absent key means "default", not None (save() only sets defaults on new docs)
		defaults = frappe.new_doc("DocType", as_dict=True)
		for key in (*IGNORED_KEYS, "name"):
			defaults.pop(key, None)
		doc.update_if_missing(defaults)
		db_values = frappe.db.get_value("DocType", name, ["creation", "owner", "modified"], as_dict=True)
		doc.name = name
		doc.creation = db_values.creation
		doc.owner = db_values.owner
		doc.modified = db_values.modified
		doc.save()
	else:
		doc.insert()

	new_text = Path(expected_path).read_text()

	return {
		"doctype": name,
		"path": str(expected_path),
		"renormalized": new_text != original_text,
		"warnings": warnings,
	}


def _resolve_target(target: str) -> tuple[str, dict]:
	"""Resolve a DocType name or JSON file path to (absolute path, parsed JSON)."""
	looks_like_path = target.endswith(".json") or os.path.sep in target

	if looks_like_path:
		path = os.path.abspath(target)
		if not os.path.isfile(path) and not os.path.isabs(target):
			# bench runs frappe commands with cwd set to the sites directory;
			# also try resolving relative to the bench root
			bench_root_path = os.path.abspath(os.path.join("..", target))
			if os.path.isfile(bench_root_path):
				path = bench_root_path
		if not os.path.isfile(path):
			frappe.throw(_("File not found: {0}").format(path), DocTypeSyncError)
	else:
		module = frappe.db.get_value("DocType", target, "module")
		if not module:
			frappe.throw(
				_(
					"DocType {0} does not exist on this site. For a new DocType, pass the path to its JSON file."
				).format(target),
				DocTypeSyncError,
			)
		path = _expected_export_path(module, target)
		if not os.path.isfile(path):
			frappe.throw(
				_("Exported file for DocType {0} not found at {1}").format(target, path), DocTypeSyncError
			)

	try:
		data = frappe.get_file_json(path)
	except ValueError as e:
		frappe.throw(_("Invalid JSON in {0}: {1}").format(path, e), DocTypeSyncError)

	return path, data


def _expected_export_path(module: str, name: str) -> str:
	try:
		folder = get_doc_path(module, "DocType", name)
	except (frappe.DoesNotExistError, ImportError):
		frappe.throw(
			_("Module {0} does not belong to any installed app on this site").format(module),
			DocTypeSyncError,
		)
	return os.path.join(folder, f"{scrub(name)}.json")


def _detect_possible_renames(name: str, data: dict) -> list[str]:
	"""Flag removed+added field pairs of the same fieldtype as possible renames.

	A rename done by drop-and-recreate silently loses the column's data; the right tool
	is a patch using frappe.model.utils.rename_field.
	"""
	db_fields = {
		field.fieldname: field.fieldtype
		for field in frappe.get_all(
			"DocField",
			filters={"parent": name, "parenttype": "DocType"},
			fields=["fieldname", "fieldtype"],
		)
		if field.fieldtype not in no_value_fields
	}
	incoming = {
		field.get("fieldname"): field.get("fieldtype")
		for field in data.get("fields", [])
		if field.get("fieldtype") not in no_value_fields
	}

	removed = set(db_fields) - set(incoming)
	added = set(incoming) - set(db_fields)

	warnings = []
	for old_fieldname in sorted(removed):
		candidates = sorted(a for a in added if incoming[a] == db_fields[old_fieldname])
		if candidates:
			warnings.append(
				f"Field '{old_fieldname}' was removed while '{', '.join(candidates)}' of the same "
				f"fieldtype was added. If this is a rename, dropping and re-adding loses the column's "
				f"data — write a patch using frappe.model.utils.rename_field instead."
			)
	return warnings
