import frappe


def execute():
	frappe.db.sql(
		"""
        DELETE from `tabDocType`
        WHERE name = 'Feedback Request'
    """
	)
