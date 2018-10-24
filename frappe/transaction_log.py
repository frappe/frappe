def log_insert(doc):
    make_log(doc.doctype, doc.name, 'INSERT')

def log_update(doc):
    make_log(doc.doctype, doc.name, 'UPDATE')

def log_rename(doctype, old, new, merge):
    make_log(doctype, old, 'RENAME', json.dumps({
        'new_name': new,
        'merge': merge,
    }))

def log_delete(doctype, name, **kwargs):
    make_log(doctype, name, 'DELETE', json.dumps(kwargs))

def make_log(doctype, name, action, actiondata=''):
    frappe.db.sql('''
        INSERT
            into
        `tabTransaction Log`(
            `doctype`
            `docname`,
            `action`,
            `actiondata`
        ) values (
            %(doctype)s,
            %(docname)s,
            %(action)s,
            %(actiondata)s
        )
    ''', {
        'doctype': doctype,
        'name': name,
        'action': action,
        'actiondata': actiondata,
    })
