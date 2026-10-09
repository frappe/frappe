# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import hashlib
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

		file_path: DF.SmallText
		migration_hash: DF.Data
	# end: auto-generated types

	_DOCTYPE_NAME = "Migration Hash"


def get_relative_file_path(path: str) -> str:
	"""Return the path from the bench's apps folder, so a stored hash survives a bench move."""
	apps_path = os.path.join(get_bench_path(), "apps")
	return os.path.relpath(os.path.realpath(path), os.path.realpath(apps_path))


def get_migration_hash_name(file_path: str) -> str:
	"""Return the record name for a relative file path.

	A path can be longer than an indexed column allows, so the name is a fixed-length digest of it.
	"""
	return hashlib.sha256(file_path.encode()).hexdigest()


def get_migration_hash(path: str) -> str | None:
	"""Return the hash of the file when it was last synced.

	The table is missing while a new site imports the doctypes that come before this one.
	"""
	if not frappe.db.table_exists("Migration Hash"):
		return None

	name = get_migration_hash_name(get_relative_file_path(path))
	return frappe.db.get_value("Migration Hash", name, "migration_hash")


def set_migration_hash(path: str, migration_hash: str) -> None:
	if not frappe.db.table_exists("Migration Hash"):
		return

	file_path = get_relative_file_path(path)
	name = get_migration_hash_name(file_path)
	if frappe.db.exists("Migration Hash", name):
		frappe.db.set_value("Migration Hash", name, "migration_hash", migration_hash, update_modified=False)
		return

	frappe.get_doc(
		{"doctype": "Migration Hash", "name": name, "file_path": file_path, "migration_hash": migration_hash}
	).insert(ignore_permissions=True)


def delete_migration_hashes(app: str) -> None:
	"""Delete the hashes of an app's files, for when the app is removed from the site."""
	if not frappe.db.table_exists("Migration Hash"):
		return

	frappe.db.delete("Migration Hash", {"file_path": ("like", f"{app}/%")})
