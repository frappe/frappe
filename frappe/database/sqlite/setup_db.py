import os
import shutil
import sys
from pathlib import Path

import click

import frappe
from frappe.database.db_manager import DbManager


def get_sqlite_version() -> str:
	return frappe.db.sql("select sqlite_version()")[0][0]


def setup_database(force, verbose):
	frappe.local.session = frappe._dict({"user": "Administrator"})

	root_conn = get_root_connection()
	root_conn.close()


def bootstrap_database(verbose, source_db=None):
	import sys

	copy_db(source_db, verbose)

	frappe.connect()
	if "tabDefaultValue" not in frappe.db.get_tables(cached=False):
		from click import secho

		secho(
			"Table 'tabDefaultValue' missing in the restored site. "
			"This happens when the backup fails to restore. Please check that the file is valid\n"
			"Do go through the above output to check the exact error message",
			fg="red",
		)
		sys.exit(1)


def copy_db(db_file=None, verbose=False):
	if verbose:
		print("Starting database import...")
	db_name = frappe.conf.db_name
	if not db_file:
		db_file = os.path.join(os.path.dirname(__file__), "framework_sqlite.db")
	db_path = Path(db_file)
	if not db_path.exists():
		click.secho(f"Database {db_path.as_posix()} does not exist", fg="red")
		sys.exit(1)

	destination_db_folder = Path(frappe.get_site_path()) / "db"
	if not destination_db_folder.exists():
		destination_db_folder.mkdir()
	destination_db_path = destination_db_folder / f"{db_name}.db"

	if db_path.suffix == ".gz":
		import gzip

		with gzip.open(db_file, "rb") as input, open(destination_db_path, "wb") as output:
			shutil.copyfileobj(input, output)

	else:
		shutil.copy(db_path, destination_db_path)
	if verbose:
		print("Imported from database {}".format(db_path))


def drop_database(db_name: str):
	Path(db_name).unlink(missing_ok=True)


def get_root_connection():
	frappe.local.flags.root_connection = frappe.database.get_db(
		cur_db_name=frappe.conf.db_name,
	)

	return frappe.local.flags.root_connection
