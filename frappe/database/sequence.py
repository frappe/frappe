from frappe import db, scrub

# NOTE:
# FOR MARIADB - using no cache - as during backup, if the sequence was used in anyform,
# it drops the cache and uses the next non cached value in setval query and
# puts that in the backup file, which will start the counter
# from that value when inserting any new record in the doctype.
# By default the cache is 1000 which will mess up the sequence when
# using the system after a restore.
#
# Another case could be if the cached values expire then also there is a chance of
# the cache being skipped.
#
# FOR POSTGRES - The sequence cache for postgres is per connection.
# Since we're opening and closing connections for every request this results in skipping the cache
# to the next non-cached value hence not using cache in postgres.
# ref: https://stackoverflow.com/questions/21356375/postgres-9-0-4-sequence-skipping-numbers
SEQUENCE_CACHE = 0

# SQLite has no native sequences. We emulate them with a small bookkeeping table
# so autoname:autoincrement doctypes can be named the same way as on
# MariaDB/Postgres - by fetching a value before the insert. The emulation
# self-seeds from existing rows, so no separate sequence object needs to be
# created when a table is set up.
SQLITE_SEQUENCE_TABLE = "__frappe_sqlite_sequences"


def create_sequence(
	doctype_name: str,
	*,
	slug: str = "_id_seq",
	temporary: bool = False,
	check_not_exists: bool = False,
	cycle: bool = False,
	cache: int = SEQUENCE_CACHE,
	start_value: int = 0,
	increment_by: int = 0,
	min_value: int = 0,
	max_value: int = 0,
) -> str:
	sequence_name = scrub(doctype_name + slug)

	if db.db_type == "sqlite":
		# `current` stores the last value handed out; nextval returns
		# current + increment. Seed it so the first nextval returns `start_value`
		# (defaulting to min_value, then 1 - matching postgres defaults).
		increment = increment_by or 1
		minv = min_value or 1
		maxv = max_value or None
		start = start_value or minv
		current = start - increment
		# Write the declared definition. On conflict we only adopt a row that is
		# still implicit (declared = 0, e.g. one set_next_val/naming created): the
		# declaration is authoritative, so it overwrites the placeholder counter and
		# definition wholesale - a placeholder `current` was only meaningful for the
		# default step, so keeping it would skew a custom increment. An
		# already-declared row is left untouched, so recreating never resets it.
		# Safe: f-string interpolates only the trusted SQLITE_SEQUENCE_TABLE constant.
		# nosemgrep
		db.sql(
			f"INSERT INTO `{SQLITE_SEQUENCE_TABLE}` "
			"(name, current, increment, min_value, max_value, cycle, declared) "
			"VALUES (%s, %s, %s, %s, %s, %s, 1) "
			"ON CONFLICT(name) DO UPDATE SET "
			"current = excluded.current, increment = excluded.increment, "
			"min_value = excluded.min_value, max_value = excluded.max_value, "
			"cycle = excluded.cycle, declared = 1 "
			"WHERE declared = 0",
			(sequence_name, current, increment, minv, maxv, 1 if cycle else 0),
		)
		return sequence_name

	query = "create sequence" if not temporary else "create temporary sequence"

	if check_not_exists:
		query += " if not exists"

	query += f" {sequence_name}"

	if increment_by:
		# default is 1
		query += f" increment by {increment_by}"

	if min_value:
		# default is 1
		query += f" minvalue {min_value}"

	if max_value:
		query += f" maxvalue {max_value}"

	if start_value:
		# default is 1
		query += f" start {start_value}"

	# in postgres, the default is cache 1 / no cache
	if cache:
		query += f" cache {cache}"
	elif db.db_type == "mariadb":
		query += " nocache"

	if not cycle:
		# in postgres, default is no cycle
		if db.db_type == "mariadb":
			query += " nocycle"
	else:
		query += " cycle"

	db.sql_ddl(query)

	return sequence_name


def get_next_val(doctype_name: str, slug: str = "_id_seq") -> int:
	if db.db_type == "sqlite":
		return _sqlite_get_next_val(doctype_name, slug)

	sequence_name = scrub(f"{doctype_name}{slug}")

	if db.db_type == "postgres":
		sequence_name = f"'\"{sequence_name}\"'"
	elif db.db_type == "mariadb":
		sequence_name = f"`{sequence_name}`"

	try:
		return db.sql(f"SELECT nextval({sequence_name})")[0][0]
	except IndexError:
		raise db.SequenceGeneratorLimitExceeded


def set_next_val(
	doctype_name: str, next_val: int, *, slug: str = "_id_seq", is_val_used: bool = False
) -> None:
	if db.db_type == "sqlite":
		sequence_name = scrub(doctype_name + slug)
		# Persist the value even if the sequence row doesn't exist yet (e.g. an
		# explicit integer name on a brand-new autoincrement doctype): create it
		# as an implicit row so a later create_sequence can still declare it. Match
		# SETVAL semantics: if next_val was already consumed the next nextval
		# returns next_val + increment, otherwise it returns next_val itself. A new
		# implicit sequence has the default increment of 1.
		# Safe: f-string interpolates only the trusted SQLITE_SEQUENCE_TABLE constant.
		# nosemgrep
		db.sql(
			f"INSERT INTO `{SQLITE_SEQUENCE_TABLE}` (name, current) VALUES (%s, %s) "
			"ON CONFLICT(name) DO UPDATE SET current = %s - (CASE WHEN %s THEN 0 ELSE increment END)",
			(sequence_name, next_val if is_val_used else next_val - 1, next_val, 1 if is_val_used else 0),
		)
		return

	is_val_used = "false" if not is_val_used else "true"

	db.multisql(
		{
			"postgres": f"SELECT SETVAL('\"{scrub(doctype_name + slug)}\"', {next_val}, {is_val_used})",
			"mariadb": f"SELECT SETVAL(`{scrub(doctype_name + slug)}`, {next_val}, {is_val_used})",
		}
	)


def create_missing_sequences() -> list[str]:
	"""Recreate sequences for autoincrement doctypes whose sequence object is missing."""
	import frappe
	from frappe.query_builder.functions import Max

	if db.db_type == "sqlite":
		return []

	doctypes = frappe.get_all(
		"DocType",
		filters={"autoname": "autoincrement", "issingle": 0, "is_virtual": 0},
		pluck="name",
	)
	if not doctypes:
		return []

	existing = _get_existing_sequences()
	created = []

	for doctype in doctypes:
		if scrub(f"{doctype}_id_seq") in existing:
			continue

		# align past existing rows to avoid name collisions; empty tables fall
		# back to the default start (1), same as normal sequence creation
		table = frappe.qb.DocType(doctype)
		max_name = frappe.qb.from_(table).select(Max(table["name"])).run()[0][0]
		create_sequence(doctype, check_not_exists=True, start_value=int(max_name) + 1 if max_name else 0)
		created.append(doctype)

	return created


# --- helpers ---------------------------------------------------------------


def _sqlite_get_next_val(doctype_name: str, slug: str) -> int:
	sequence_name = scrub(f"{doctype_name}{slug}")

	# The backing table is created at site setup (create_sequence_table), so the
	# read-modify-write below can assume it exists - no per-call DDL on the hot path.
	# Fast, fully-atomic path for unbounded sequences (which is every autoname
	# sequence): the read-modify-write happens as one statement under SQLite's
	# write lock, so concurrent callers can never be handed the same value.
	# Requires SQLite >= 3.35 for RETURNING, well below any version frappe targets.
	# Safe: f-string interpolates only the trusted SQLITE_SEQUENCE_TABLE constant.
	# nosemgrep
	row = db.sql(
		f"UPDATE `{SQLITE_SEQUENCE_TABLE}` SET current = current + increment "
		"WHERE name = %s AND max_value IS NULL RETURNING current",
		(sequence_name,),
	)
	if row:
		return row[0][0]

	# Safe: f-string interpolates only the trusted SQLITE_SEQUENCE_TABLE constant.
	# nosemgrep
	existing = db.sql(
		f"SELECT max_value FROM `{SQLITE_SEQUENCE_TABLE}` WHERE name = %s",
		(sequence_name,),
	)
	if not existing:
		# Auto-created (un-declared) sequence, e.g. autoname naming: seed past any
		# existing rows so emulated names never collide, and leave it unbounded.
		# The upsert makes a concurrent first-use increment the freshly-created
		# row instead of colliding on the primary key.
		# Safe: f-string interpolates only the trusted SQLITE_SEQUENCE_TABLE constant.
		# nosemgrep
		row = db.sql(
			f"INSERT INTO `{SQLITE_SEQUENCE_TABLE}` (name, current) VALUES (%s, %s) "
			"ON CONFLICT(name) DO UPDATE SET current = current + increment RETURNING current",
			(sequence_name, _sqlite_seed_value(doctype_name)),
		)
		return row[0][0]

	if existing[0][0] is None:  # pragma: no cover - only reachable under a concurrent first-use race
		# Unbounded row created concurrently between the statements above; the
		# fast path missed it, so increment it atomically now.
		# Safe: f-string interpolates only the trusted SQLITE_SEQUENCE_TABLE constant.
		# nosemgrep
		return db.sql(
			f"UPDATE `{SQLITE_SEQUENCE_TABLE}` SET current = current + increment "
			"WHERE name = %s RETURNING current",
			(sequence_name,),
		)[0][0]

	# Bounded sequence (max_value set): advance / cycle in one statement so the
	# read-modify-write is atomic. The WHERE clause withholds the row when a
	# non-cycling sequence would overflow, so RETURNING comes back empty and we
	# raise instead of handing out a duplicate or out-of-range value.
	# Safe: f-string interpolates only the trusted SQLITE_SEQUENCE_TABLE constant.
	# nosemgrep
	row = db.sql(
		f"UPDATE `{SQLITE_SEQUENCE_TABLE}` SET current = "
		"CASE WHEN current + increment > max_value THEN min_value ELSE current + increment END "
		"WHERE name = %s AND (current + increment <= max_value OR cycle) RETURNING current",
		(sequence_name,),
	)
	if not row:
		raise db.SequenceGeneratorLimitExceeded
	return row[0][0]


def _sqlite_seed_value(doctype_name: str) -> int:
	# Seed past any rows that already exist so emulated names never collide with
	# pre-existing ones (mirrors how create_missing_sequences seeds real ones).
	# Cast to integer so a non-numeric legacy name (from import or an old naming
	# scheme) doesn't break MAX; built via the query builder so the table name is
	# safely quoted.
	import frappe
	from frappe.query_builder.functions import Cast_, Max

	table = frappe.qb.DocType(doctype_name)
	max_name = frappe.qb.from_(table).select(Max(Cast_(table.name, "integer"))).run()[0][0]
	return int(max_name or 0) + 1


def _get_existing_sequences() -> set[str]:
	if db.db_type == "postgres":
		rows = db.sql(
			"""SELECT sequence_name FROM information_schema.sequences
			WHERE sequence_schema = 'public'"""
		)
	else:
		rows = db.sql(
			"""SELECT TABLE_NAME FROM information_schema.TABLES
			WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'SEQUENCE'"""
		)
	return {r[0] for r in rows}
