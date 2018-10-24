def insert(doc):
    make_log(doc.doctype, doc.name, 'INSERT')

def update(doc):
    make_log(doc.doctype, doc.name, 'UPDATE')

def rename(doctype, old, new, merge):
    make_log(doctype, old, 'RENAME', json.dumps({
        'new_name': new,
        'merge': merge,
    }))

def delete(doctype, name):
    make_log(doctype, name, 'DELETE')

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
