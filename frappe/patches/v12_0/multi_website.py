import frappe
from frappe import _

def execute():
    frappe.reload_doc('website', 'doctype', 'website')

    convert_to_non_single('Website Settings', 'Website', _('Default'),
        'website_name', {'is_default': 1}, ['Website Hostname'])

    website_script = frappe.db.get_single_value('Website Script', 'javascript')
    frappe.db.set_value('Website', _('Default'), 'website_script', website_script)
    frappe.delete_doc('DocType', 'Website Script')

def convert_to_non_single(old_dt, new_dt, dn, name_field, attrs=None, exclude_tables=[]):
    old_values = frappe.db.get_values_from_single('*', None, old_dt, as_dict=1)
    if not old_values:
        return
    
    old_values = old_values[0]
    if old_values.get('docstatus'):
        del old_values['docstatus']

    new_doc = frappe.new_doc(new_dt)
    setattr(new_doc, name_field, dn)
    if attrs:
        new_doc.update(attrs)
    new_doc.update(old_values)
    new_doc.save()
    
    meta = frappe.get_meta(new_dt)
    for df in meta.get_table_fields():
        if df.options not in exclude_tables:
            frappe.db.sql("update `tab%s` set parenttype=%s, parent=%s where parenttype=%s" \
                % (df.options, '%s', '%s', '%s'), (new_dt, dn, old_dt))

    old_attachments = frappe.get_list('File', {'attached_to_doctype': old_dt})
    if old_attachments:
        for f in old_attachments:
            file_doc = frappe.get_doc('File', f.name)
            file_doc.attached_to_doctype = new_dt
            file_doc.attached_to_name = dn
            file_doc.save()
    
    frappe.db.sql("UPDATE `tabVersion` SET `ref_doctype`=%s, `docname`=%s WHERE `ref_doctype`=%s",
		(new_dt, dn, old_dt))

    # All things custom (singles can't have custom fields)
    frappe.db.sql("UPDATE `tabCustom Script` SET dt=%s WHERE dt=%s",
        (new_dt, old_dt))
    frappe.db.sql("UPDATE `tabCustom DocPerm` SET parent=%s WHERE parent=%s",
        (new_dt, old_dt))

    # Delete old data
    frappe.db.sql("DELETE FROM tabSingles WHERE doctype=%s", old_dt)