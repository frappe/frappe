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
		_sqlite_ensure_table()
		# `current` stores the last value handed out; nextval returns
		# current + increment. Seed it so the first nextval returns `start_value`
		# (defaulting to min_value, then 1 - matching postgres defaults).
		increment = increment_by or 1
		minv = min_value or 1
		maxv = max_value or None
		start = start_value or minv
		current = start - increment
		verb = "INSERT OR IGNORE" if check_not_exists else "INSERT"
		db.sql(
			f"{verb} INTO `{SQLITE_SEQUENCE_TABLE}` "
			"(name, current, increment, min_value, max_value, cycle) "
			"VALUES (%s, %s, %s, %s, %s, %s)",
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
		_sqlite_ensure_table()
		sequence_name = scrub(doctype_name + slug)
		row = db.sql(f"SELECT increment FROM `{SQLITE_SEQUENCE_TABLE}` WHERE name = %s", (sequence_name,))
		increment = row[0][0] if row else 1
		# Match SETVAL semantics: if next_val was already consumed, the following
		# nextval returns next_val + increment; otherwise it returns next_val itself.
		current = next_val if is_val_used else next_val - increment
		db.sql(
			f"INSERT INTO `{SQLITE_SEQUENCE_TABLE}` (name, current) VALUES (%s, %s) "
			"ON CONFLICT(name) DO UPDATE SET current = excluded.current",
			(sequence_name, current),
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
	_sqlite_ensure_table()

	# Fast, fully-atomic path for unbounded sequences (which is every autoname
	# sequence): the read-modify-write happens as one statement under SQLite's
	# write lock, so concurrent callers can never be handed the same value.
	# Requires SQLite >= 3.35 for RETURNING, well below any version frappe targets.
	row = db.sql(
		f"UPDATE `{SQLITE_SEQUENCE_TABLE}` SET current = current + increment "
		"WHERE name = %s AND max_value IS NULL RETURNING current",
		(sequence_name,),
	)
	if row:
		return row[0][0]

	existing = db.sql(
		f"SELECT current, increment, min_value, max_value, cycle "
		f"FROM `{SQLITE_SEQUENCE_TABLE}` WHERE name = %s",
		(sequence_name,),
	)
	if not existing:
		# Auto-created (un-declared) sequence, e.g. autoname naming: seed past any
		# existing rows so emulated names never collide, and leave it unbounded.
		next_val = _sqlite_seed_value(doctype_name)
		db.sql(
			f"INSERT INTO `{SQLITE_SEQUENCE_TABLE}` (name, current) VALUES (%s, %s)",
			(sequence_name, next_val),
		)
		return next_val

	# Bounded sequence (max_value set): honour increment / max_value / cycle.
	current, increment, min_value, max_value, cycle = existing[0]
	next_val = current + increment
	if max_value is not None and next_val > max_value:
		if cycle:
			next_val = min_value
		else:
			raise db.SequenceGeneratorLimitExceeded
	db.sql(
		f"UPDATE `{SQLITE_SEQUENCE_TABLE}` SET current = %s WHERE name = %s",
		(next_val, sequence_name),
	)
	return next_val


def _sqlite_ensure_table() -> None:
	db.sql_ddl(
		f"CREATE TABLE IF NOT EXISTS `{SQLITE_SEQUENCE_TABLE}` ("
		"name TEXT PRIMARY KEY, "
		"current INTEGER NOT NULL, "
		"increment INTEGER NOT NULL DEFAULT 1, "
		"min_value INTEGER NOT NULL DEFAULT 1, "
		"max_value INTEGER, "
		"cycle INTEGER NOT NULL DEFAULT 0)"
	)


def _sqlite_seed_value(doctype_name: str) -> int:
	# Seed past any rows that already exist so emulated names never collide with
	# pre-existing ones (mirrors how create_missing_sequences seeds real ones).
	max_name = db.sql(f"SELECT MAX(CAST(name AS INTEGER)) FROM `tab{doctype_name}`")[0][0]
	return (max_name or 0) + 1


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
