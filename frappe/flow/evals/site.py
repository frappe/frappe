# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Which sites may run evals, and the snapshot that puts a site back before every run."""

from contextlib import contextmanager, suppress
from functools import wraps

import click

import frappe
from frappe.utils import create_batch, now

LIST = "__flow_eval"
PREFIX = "__flow_eval_"


def check_site() -> None:
	"""Refuse a site whose own config does not allow evals, or that is not on MariaDB."""
	own = frappe.get_file_json(frappe.get_site_path("site_config.json"))
	if str(own.get("allow_flow_evals")).lower() not in ("1", "true"):
		raise click.ClickException(
			"Flow evals are disabled for the site!\n"
			"Evals put every table back to how it was when the command started, so anything else "
			"written to the site while it runs is lost. Use a site made for this.\n"
			f"bench --site {frappe.local.site} set-config allow_flow_evals true"
		)
	if frappe.conf.db_type not in (None, "mariadb"):
		raise click.ClickException("Flow evals need a MariaDB site.")


_held = 0


@contextmanager
def lock():
	"""The site's eval lock; every snapshot operation holds it, so two commands never share a copy."""
	from frappe.utils.synchronization import LockTimeoutError, filelock

	global _held
	if _held:
		_held += 1
		try:
			yield
		finally:
			_held -= 1
		return
	try:
		with filelock("flow_eval", timeout=5):
			_held = 1
			try:
				yield
			finally:
				_held = 0
	except LockTimeoutError:
		raise click.ClickException("Another flow-eval is running on this site.") from None


def _locked(method):
	@wraps(method)
	def inner(*args, **kwargs):
		with lock():
			return method(*args, **kwargs)

	return inner


class Snapshot:
	"""Table names in its SQL come from the database's own table list, never from input.

	A copy of every table in the site's own database, kept in tables named `__flow_eval_<n>`.
	The table `__flow_eval` lists which copy is whose; its row with an empty name marks the copy
	whole. Nothing is held in memory, so a later command can restore what a killed one took."""

	def __enter__(self):
		self.take()
		return self

	def __exit__(self, *exc):
		self.restore()
		self.drop()

	@_locked
	def take(self) -> None:
		if self.exists():
			raise click.ClickException("A snapshot already exists; run the command again to recover it.")
		try:
			frappe.db.sql_ddl(f"create table `{LIST}` (tbl varchar(64) primary key, copy varchar(64))")
			for n, table in enumerate(_tables()):
				copy = f"{PREFIX}{n}"
				frappe.db.sql_ddl(f"create table `{copy}` like `{table}`")
				frappe.db.sql(  # nosemgrep: frappe-sql-format-injection
					f"insert into `{copy}` select * from `{table}`"
				)
				frappe.db.sql("insert into __flow_eval values (%s, %s)", (table, copy))
				frappe.db.commit()  # DDL commits anyway; nosemgrep: frappe-manual-commit
			frappe.db.sql("insert into __flow_eval values ('', %s)", now())
			frappe.db.commit()  # DDL commits anyway; nosemgrep: frappe-manual-commit
		except BaseException:
			frappe.db.rollback()
			self.drop()
			raise

	def exists(self) -> bool:
		return LIST in _tables(own=False)

	def complete(self) -> str | None:
		"""When the whole copy was taken; None while it is partial or missing."""
		if not self.exists():
			return None
		return (frappe.db.sql("select copy from __flow_eval where tbl = ''", pluck=True) or [None])[0]

	@_locked
	def restore(self) -> bool:
		"""Rebuild every table whose rows or columns differ from its copy, and drop tables the list
		does not name. Does nothing unless the copy is whole: a partial list would drop real tables.
		A listed table whose copy is missing is left as it is."""
		if not self.complete():
			return False
		listed = dict(frappe.db.sql("select tbl, copy from __flow_eval where tbl != ''"))
		live, present = set(_tables()), set(_tables(own=False))
		for table in live - set(listed):
			frappe.db.sql_ddl(f"drop table `{table}`")
		copies = {table: copy for table, copy in listed.items() if copy in present}
		sums, columns = _checksums([*copies, *copies.values()]), _columns()
		for table, copy in copies.items():
			if (
				sums.get(table) is not None
				and sums[table] == sums[copy]
				and columns.get(table) == columns.get(copy)
			):
				continue
			# rebuilt beside it and swapped in, so the table is never missing
			new, old = f"{PREFIX}new", f"{PREFIX}old"
			frappe.db.sql_ddl(f"drop table if exists `{new}`, `{old}`")
			frappe.db.sql_ddl(f"create table `{new}` like `{copy}`")
			frappe.db.sql(  # nosemgrep: frappe-sql-format-injection
				f"insert into `{new}` select * from `{copy}`"
			)
			frappe.db.commit()  # DDL commits anyway; nosemgrep: frappe-manual-commit
			if table in live:
				frappe.db.sql_ddl(f"rename table `{table}` to `{old}`, `{new}` to `{table}`")
				frappe.db.sql_ddl(f"drop table `{old}`")
			else:
				frappe.db.sql_ddl(f"rename table `{new}` to `{table}`")
		frappe.db.commit()  # DDL commits anyway; nosemgrep: frappe-manual-commit
		frappe.clear_cache()
		return True

	@_locked
	def drop(self) -> None:
		"""Unmark the copy first, so a kill part-way never leaves a list that looks whole."""
		if self.exists():
			frappe.db.sql("delete from __flow_eval where tbl = ''")
			frappe.db.commit()  # DDL commits anyway; nosemgrep: frappe-manual-commit
		for table in _tables(own=False):
			if table.startswith(PREFIX):
				frappe.db.sql_ddl(f"drop table `{table}`")
		frappe.db.sql_ddl(f"drop table if exists `{LIST}`")

	@_locked
	def recover(self) -> str | None:
		"""Put back what a killed command's snapshot holds, and drop it. Returns when it was taken."""
		if not self.exists():
			return None
		for session in frappe.get_all("Flow Run", {"status": "Running"}, pluck="session", distinct=True):
			with suppress(Exception):
				frappe.get_doc("Flow Session", session).abort()
		taken = self.complete()
		self.restore()
		self.drop()
		return taken


def _tables(own: bool = True) -> list[str]:
	"""The database's base tables; with `own`, not the snapshot's."""
	tables = frappe.db.sql("show full tables where Table_type = 'BASE TABLE'", pluck=True)
	return [t for t in tables if not (own and t.startswith(LIST))]


def _checksums(tables: list[str]) -> dict[str, int]:
	sums = {}
	for batch in create_batch(tables, 100):
		query = "checksum table " + ", ".join(f"`{t}`" for t in batch)
		rows = frappe.db.sql(query)  # names from show tables; nosemgrep: frappe-sql-format-injection
		for name, value in rows:
			sums[name.split(".", 1)[1]] = value
	return sums


def _columns() -> dict[str, list[tuple[str, str]]]:
	columns = {}
	for table, column, kind in frappe.db.sql(
		"""select table_name, column_name, column_type from information_schema.columns
		where table_schema = database() order by table_name, ordinal_position"""
	):
		columns.setdefault(table, []).append((column, kind))
	return columns
