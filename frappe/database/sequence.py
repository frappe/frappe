from frappe import db, scrub


def create_sequence(
	doctype_name: str,
	*,
	slug: str = "_id_seq",
	check_not_exists: bool = False,
	cycle: bool = False,
	cache: int = 0,
	start_value: int = 0,
	increment_by: int = 0,
	min_value: int = 0,
	max_value: int = 0
) -> str:

	query = "create sequence"
	sequence_name = scrub(doctype_name + slug)

	if check_not_exists:
		query += " if not exists"

	query += f" {sequence_name}"

	if cache:
		query += f" cache {cache}"
	else:
		# in postgres, the default is cache 1
		if db.db_type == "mariadb":
			query += " nocache"

	if start_value:
		# default is 1
		query += f" start with {start_value}"

	if increment_by:
		# default is 1
		query += f" increment by {increment_by}"

	if min_value:
		# default is 1
		query += f" min value {min_value}"

	if max_value:
		query += f" max value {max_value}"

	if not cycle:
		if db.db_type == "mariadb":
			query += " nocycle"
	else:
		query += " cycle"

	db.sql(query)

	return sequence_name


def get_next_val(doctype_name: str, slug: str = "_id_seq") -> int:
	if db.db_type == "postgres":
		return db.sql(f"select nextval(\'\"{scrub(doctype_name + slug)}\"\')")[0][0]
	return db.sql(f"select nextval(`{scrub(doctype_name + slug)}`)")[0][0]


def set_next_val(
	doctype_name: str,
	next_val: int,
	*,
	slug: str = "_id_seq",
	is_val_used :bool = False
) -> None:

	if not is_val_used:
		is_val_used = 0 if db.db_type == "mariadb" else "f"
	else:
		is_val_used = 1 if db.db_type == "mariadb" else "t"

	if db.db_type == "postgres":
		db.sql(f"SELECT SETVAL('\"{scrub(doctype_name + slug)}\"', {next_val}, '{is_val_used}')")
	else:
		db.sql(f"SELECT SETVAL(`{scrub(doctype_name + slug)}`, {next_val}, {is_val_used})")
