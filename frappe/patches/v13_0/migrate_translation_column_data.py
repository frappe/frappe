import frappe

def execute():
	frappe.reload_doctype('Translation')
	frappe.db.sql("""
		UPDATE `tabTranslation`
			SET
				translated_text=target_name,
				source_text=source_name,
				contribution_docname=contributed_translation_doctype_name,
				contribution_status=(CASE status
					WHEN 'Deleted' THEN 'Rejected'
					ELSE ''
					END),
				contributed=0
	""")
