import frappe

def validate(doc,method):
    file_extension = doc.file_url.split('.')[-1].lower()
    extension = frappe.db.get_list("File Extension",pluck = "name1")
    if extension and file_extension not in extension :
        frappe.throw(f'Only extension {extension} files are allowed')
