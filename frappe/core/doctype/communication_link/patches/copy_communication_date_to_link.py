import frappe


# copy communication_date from Communication to Communication Link
def execute():
	frappe.db.multisql(
		{
			"mariadb": """
				UPDATE `tabCommunication Link` cl
				INNER JOIN `tabCommunication` c ON cl.parent = c.name
				SET cl.communication_date = c.communication_date
				WHERE c.communication_date IS NOT NULL
			""",
			"postgres": """
				UPDATE "tabCommunication Link" cl
				SET communication_date = c.communication_date
				FROM "tabCommunication" c
				WHERE cl.parent = c.name
				  AND c.communication_date IS NOT NULL
			""",
		}
	)
