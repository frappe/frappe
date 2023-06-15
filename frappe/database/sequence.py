import frappe
from frappe import db, scrub
from frappe.utils import cint


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


def recreate_sequences() -> None:
	"""Repair missing sequences for integer PK DocTypes"""

	pk_doctypes = _get_doctypes_with_int_pk()

	for doctype in pk_doctypes:
		frappe.db.create_sequence(doctype, check_not_exists=True, cache=False)

		next_val = _get_current_max_value(doctype) + 1

		frappe.db.logger.warning(f"Setting DB next val of sequence {doctype} to {next_val}")
		set_next_val(doctype, next_val)


def _get_doctypes_with_int_pk() -> list[str]:
	from frappe.model import log_types

	def pk_type_is_int(doctype: str) -> bool:
		if frappe.db.table_exists(doctype):
			return "bigint" in frappe.db.get_column_type(doctype, "name")
		return False

	pk_doctypes = frappe.get_all("DocType", {"autoname": "autoincrement"}, pluck="name")

	# These are implicitly assumed to be autoincrement
	pk_doctypes += list(log_types)

	return [d for d in pk_doctypes if pk_type_is_int(d)]


def _get_current_max_value(doctype) -> int:
	from frappe.query_builder.functions import Max

	table = frappe.qb.DocType(doctype)
	current_val = frappe.qb.from_(table).select(Max(table.name)).run(pluck=True)

	return cint(current_val[0])
