# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import os

import frappe
from frappe.model.document import Document
from frappe.utils import get_bench_path


class MigrationHash(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		file_path: DF.Data
		migration_hash: DF.Data
	# end: auto-generated types

	_DOCTYPE_NAME = "Migration Hash"


def get_relative_file_path(path: str) -> str:
	"""Return the path from the bench's apps folder, so a stored hash survives a bench move."""
	apps_path = os.path.join(get_bench_path(), "apps")
	return os.path.relpath(os.path.realpath(path), os.path.realpath(apps_path))


def get_migration_hash(path: str) -> str | None:
	"""Return the hash of the file when it was last synced.

	The table is missing while a new site imports the doctypes that come before this one.
	"""
	if not frappe.db.table_exists("Migration Hash"):
		return None

	return frappe.db.get_value(
		"Migration Hash", {"file_path": get_relative_file_path(path)}, "migration_hash"
	)


def set_migration_hash(path: str, migration_hash: str) -> None:
	if not frappe.db.table_exists("Migration Hash"):
		return

	file_path = get_relative_file_path(path)
	name = frappe.db.get_value("Migration Hash", {"file_path": file_path})
	if name:
		frappe.db.set_value("Migration Hash", name, "migration_hash", migration_hash, update_modified=False)
		return

	frappe.get_doc(
		{"doctype": "Migration Hash", "file_path": file_path, "migration_hash": migration_hash}
	).insert(ignore_permissions=True)
