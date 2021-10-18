import frappe

def execute():
    categories = frappe.db.sql("""SELECT DISTINCT event_category FROM tabEvent""", as_list=1)
    frappe.reload_doc('desk', 'doctype', 'event_category')
    for category in categories:
        frappe.get_doc({
            'doctype' : 'Event Category',
            'event_category' : category[0]
        }).insert()