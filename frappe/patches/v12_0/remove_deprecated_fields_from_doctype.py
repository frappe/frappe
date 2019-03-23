import frappe

def execute():
	frappe.db.sql('''
		ALTER TABLE tabDocType
		DROP COLUMN IF EXISTS hide_heading,
		DROP COLUMN IF EXISTS image_view,
		DROP COLUMN IF EXISTS read_only_onload
	''')
