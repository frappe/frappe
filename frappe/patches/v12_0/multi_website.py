import os

import frappe
from frappe import _

__location__ = os.path.realpath(os.path.join(
    os.getcwd(), os.path.dirname(__file__)))

tables_list = frappe.db.get_tables()

def execute():
    website_name = _('Default')

    frappe.reload_doc('website', 'doctype', 'website')
    frappe.reload_doc('website', 'doctype', 'website_hostname')
    frappe.reload_doc('website', 'doctype', 'portal')

    # Website Settings ==> Website
    convert_to_non_single('Website Settings', 'Website', website_name,
        'website_name', {'is_default': 1}, ['Website Hostname'])

    # Portal Settings ==> Portal
    portal_name = convert_to_non_single('Portal Settings', 'Portal')
    frappe.db.set_value('Website', website_name, 'portal', portal_name)

    # Website Script (doctype ==> field)
    website_script = frappe.db.get_single_value('Website Script', 'javascript')
    frappe.db.set_value('Website', website_name, 'website_script', website_script)

    # Blog Settings (doctype ==> fields)
    blog_settings = frappe.db.get_values_from_single('*', None,
        'Blog Settings', as_dict=1)
    if blog_settings:
        blog_settings = blog_settings[0]
        for field in ['blog_title', 'blog_introduction']:
            if blog_settings.get(field):
                frappe.db.set_value('Website', website_name, field,
                    blog_settings[field])

    # About Us, Contact Us ==> Web Pages
    about_child_tables = {
        'company_history': 'Company History',
        'team_members': 'About Us Team Member'
    }
    convert_to_web_page('About Us Settings', 'about', 'about.html',
        'About Us', child_tables=about_child_tables)

    convert_to_web_page('Contact Us Settings', 'contact', 'contact.html',
        'Contact Us', javascript='contact.js')

def convert_to_non_single(old_dt, new_dt, dn=None, name_field=None,
        attrs=None, exclude_tables=None):
    # Fetch existing values
    old_values = frappe.db.get_values_from_single('*', None, old_dt, as_dict=1)

    if old_values:
        old_values = old_values[0]
        if old_values.get('docstatus'):
            del old_values['docstatus'] # To prevent error on save

    # Create new doc
    new_doc = frappe.new_doc(new_dt)
    if dn:
        setattr(new_doc, name_field, dn)
    if attrs:
        new_doc.update(attrs)
    if old_values:
        new_doc.update(old_values)
    new_doc.save()
    if not dn:
        dn = new_doc.name

    # Update child tables
    meta = frappe.get_meta(new_dt)
    if not exclude_tables:
        exclude_tables = []
    for df in meta.get_table_fields():
        if df.options not in exclude_tables:
            frappe.db.sql("update `tab%s` set parenttype=%s, parent=%s where parenttype=%s" \
                % (df.options, '%s', '%s', '%s'), (new_dt, dn, old_dt))

    # Update attachments
    old_attachments = frappe.get_list('File', {'attached_to_doctype': old_dt})
    if old_attachments:
        for f in old_attachments:
            file_doc = frappe.get_doc('File', f.name)
            file_doc.attached_to_doctype = new_dt
            file_doc.attached_to_name = dn
            file_doc.save()

    # Update Version, Custom Script and Custom Permissions
    frappe.db.sql("UPDATE `tabVersion` SET `ref_doctype`=%s, `docname`=%s WHERE `ref_doctype`=%s",
        (new_dt, dn, old_dt))
    frappe.db.sql("UPDATE `tabCustom Script` SET dt=%s WHERE dt=%s",
        (new_dt, old_dt))
    frappe.db.sql("UPDATE `tabCustom DocPerm` SET parent=%s WHERE parent=%s",
        (new_dt, old_dt))

    return dn

def convert_to_web_page(dt, route, template, title, child_tables=None, javascript=None):
    # Fetch existing values
    doc = frappe.db.get_values_from_single('*', None, dt, as_dict=1)
    if not doc or frappe.db.exists('Web Page', {'route': route}):
        return

    doc = doc[0]

    # Contact Us: sanitise query options before rendering template
    if dt == 'Contact Us Settings':
        if doc.get('query_options'):
            doc.query_options = [opt.strip() for opt
                in doc.query_options.replace(",", "\n").split("\n") if opt]
        else:
            doc.query_options = ["Sales", "Support", "General"]

    # Fetch child tables if any
    if child_tables:
        for key, val in child_tables.items():
            if 'tab' + val in tables_list:
                entries = frappe.db.sql('select * from `tab%s`' % val, as_dict=1)
                doc[key] = entries

    with open(os.path.join(__location__, template)) as f:
        template_html = f.read()

    web_page = frappe.new_doc('Web Page')
    web_page.title = doc.get('heading') or title
    web_page.route = route
    web_page.published = 1
    web_page.show_title = 0
    web_page.breadcrumbs = '[{"label": _("Home"), "route":"home"}]'
    web_page.main_section = frappe.render_template(template_html, {'doc': doc})

    if javascript:
        with open(os.path.join(__location__, javascript)) as f:
            js_code = f.read()

        web_page.insert_code = 1
        web_page.javascript = js_code

    web_page.save()