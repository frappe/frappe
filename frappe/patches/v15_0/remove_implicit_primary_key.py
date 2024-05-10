import frappe
from frappe.model.naming import is_autoincremented

possible_log_types = (
	"Version",
	"Error Log",
	"Scheduled Job Log",
	"Event Sync Log",
	"Event Update Log",
	"Access Log",
	"View Log",
	"Activity Log",
	"Energy Point Log",
	"Notification Log",
	"Email Queue",
	"DocShare",
	"Document Follow",
	"Console Log",
)


def execute():
	"""Few doctypes had int PKs even though schema didn't mention them, this requires detecting it
	at runtime which is prone to bugs and adds unnecessary overhead.

	This patch converts them back to varchar.
	"""
	for doctype in possible_log_types:
		if (
			frappe.db.exists("DocType", doctype)
			and _is_implicit_int_pk(doctype)
			and not is_autoincremented(doctype)
		):
			frappe.db.change_column_type(
				doctype,
				"name",
				type=f"varchar({frappe.db.VARCHAR_LEN})",
				nullable=True,
			)


def _is_implicit_int_pk(doctype: str) -> bool:
	query = f"""select data_type FROM information_schema.columns where column_name = 'name' and table_name = 'tab{doctype}'"""
	values = ()
	if frappe.db.db_type == "mariadb":
		query += " and table_schema = %s"
		values = (frappe.db.cur_db_name,)

	col_type = frappe.db.sql(query, values)
	return bool(col_type and col_type[0][0] == "bigint")
