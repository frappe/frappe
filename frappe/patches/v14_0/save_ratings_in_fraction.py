import nts
from nts.query_builder import DocType


def execute():
	RATING_FIELD_TYPE = "decimal(3,2)"
	rating_fields = nts.get_all(
		"DocField", fields=["parent", "fieldname"], filters={"fieldtype": "Rating"}
	)

	custom_rating_fields = nts.get_all(
		"Custom Field", fields=["dt", "fieldname"], filters={"fieldtype": "Rating"}
	)

	for _field in rating_fields + custom_rating_fields:
		doctype_name = _field.get("parent") or _field.get("dt")
		doctype = DocType(doctype_name)
		field = _field.fieldname

		# TODO: Add postgres support (for the check)
		if (
			nts.conf.db_type == "mariadb"
			and nts.db.get_column_type(doctype_name, field) == RATING_FIELD_TYPE
		):
			continue

		# commit any changes so far for upcoming DDL
		nts.db.commit()

		# alter column types for rating fieldtype
		nts.db.change_column_type(doctype_name, column=field, type=RATING_FIELD_TYPE, nullable=True)

		# update data: int => decimal
		nts.qb.update(doctype).set(doctype[field], doctype[field] / 5).run()

		# commit to flush updated rows
		nts.db.commit()
