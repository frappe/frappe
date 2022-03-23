import frappe

def execute():
    custome_deleted_doc_list = frappe.db.sql("""
        select c.name from 
        `tabCustom DocPerm` as c left join `tabDocType` as d 
        on d.name = c.parent 
        where d.name is NULL;
    """, as_dict = 1)
    for doc_name in custome_deleted_doc_list:
        frappe.db.sql("""delete from `tabCustom DocPerm` where name = '{}'""".format(doc_name.name))