import frappe


# copy communication_date from Communication to Communication Link
def execute():
	frappe.db.sql(
		"""
        update `tabCommunication Link` cl
        inner join `tabCommunication` c on cl.parent = c.name
        set cl.communication_date = c.communication_date
        where c.communication_date is not null
    """
	)
