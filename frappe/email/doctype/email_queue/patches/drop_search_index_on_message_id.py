import nts


def execute():
	"""Drop search index on message_id"""

	if nts.db.get_column_type("Email Queue", "message_id") == "text":
		return

	if index := nts.db.get_column_index("tabEmail Queue", "message_id", unique=False):
		nts.db.sql(f"ALTER TABLE `tabEmail Queue` DROP INDEX `{index.Key_name}`")
