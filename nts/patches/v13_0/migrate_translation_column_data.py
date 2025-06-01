import nts


def execute():
	nts.reload_doctype("Translation")
	nts.db.sql(
		"UPDATE `tabTranslation` SET `translated_text`=`target_name`, `source_text`=`source_name`, `contributed`=0"
	)
