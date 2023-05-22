from frappe import db, scrub


def create_sequence(
	doctype_name: str,
	*,
	slug: str = "_id_seq",
	temporary: bool = False,
	check_not_exists: bool = False,
	cycle: bool = False,
	cache: int = 0,
	start_value: int = 0,
	increment_by: int = 0,
	min_value: int = 0,
	max_value: int = 0,
) -> str:

	query = "create sequence" if not temporary else "create temporary sequence"
	sequence_name = scrub(doctype_name + slug)

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

	is_val_used = "false" if not is_val_used else "true"

	db.multisql(
		{
			"postgres": f"SELECT SETVAL('\"{scrub(doctype_name + slug)}\"', {next_val}, {is_val_used})",
			"mariadb": f"SELECT SETVAL(`{scrub(doctype_name + slug)}`, {next_val}, {is_val_used})",
		}
	)
