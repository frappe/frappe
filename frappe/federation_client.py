import frappe
from frappe.frappeclient import FrappeClient
from frappe.defaults import set_global_default
from six import string_types, iteritems
import json

def get_remote_logs():
    sync_status = frappe.db.sql('''
    SELECT
        defkey, defValue
    from
        `tabDefaultValue`
    where
        defkey=%s and parent=%s
        for update''', ("client_sync_running", "__default"), as_dict = True)

    if sync_status[0]["defValue"] == "Active":
        return

    sync_pos = frappe.db.sql('''
    SELECT
        defkey, defValue
    from
        `tabDefaultValue`
    where
        defkey=%s and parent=%s
        for update''', ("client_sync_pos", "__default"), as_dict = True)

    last_inserted_logid = sync_pos[0]["defValue"]
    current_working_logid = int(last_inserted_logid)

    # master_setup = FrappeClient(frappe.local.conf.federation_master_hostname,frappe.local.conf.federation_master_user, frappe.local.conf.federation_master_password)
    master_setup = FrappeClient(frappe.local.conf.master_node,
            frappe.local.conf.master_user,
            frappe.local.conf.master_pass)

    new_master_logs = master_setup.post_request({
        "cmd": "frappe.federation_master.send_new_logs",
        "name_threshold": current_working_logid,
        "limit": 100
    })
    for master_log in new_master_logs:
        if master_log["action"] == "INSERT":
            original_doc = master_setup.get_doc(master_log["doctype"], master_log["docname"])
            new_doc = frappe.get_doc(original_doc)
            new_doc.name = original_doc["name"]
            new_doc.insert()
        elif master_log["action"] == "UPDATE":
            updated_doc = master_setup.get_doc(master_log["doctype"], master_log["docname"])
            original_doc = frappe.get_doc(master_log["doctype"], master_log["docname"])
            for fieldname in updated_doc.keys():
                original_doc.set(fieldname, updated_doc.get(fieldname))
            original_doc.save()
        elif master_log["action"] == "RENAME":
            frappe.rename_doc(master_log["doctype"], master_log["docname"], master_log["actiondata"])
        elif master_log["action"] == "DELETE":
            frappe.delete_doc_if_exists(master_log["doctype"], master_log["docname"])

        current_working_logid = current_working_logid + 1

    set_global_default("client_sync_pos", current_working_logid)
    set_global_default("client_sync_running", "Inactive")


def chain_all(fns):
    if not fns:
        return (lambda *args: True)

    chain = []
    for fn in fns:
        if isinstance(fn, string_types):
            fn = frappe.get_attr(fn)
        chain.append(fn)

    def chained_fn(doc):
        for fn in chain:
            if not fn(doc):
                return
        return True

    return chained_fn

def get_transactional_documents():
    conf = frappe.local.conf
    transactional_doctypes = frappe.local.conf.consolidate_doctypes or []
    if not transactional_doctypes:
        return
    sync_rules = frappe.get_hooks('sync_rules')
    transactional_doctypes = {
        dt: (sync_rules or {}).get(dt, {}) for dt in transactional_doctypes
    }
    transactional_doctypes = [
        (dt, chain_all(value.get('is_new')), chain_all(value.get('preprocess')), chain_all(value.get('postprocess')))
            for dt, value in iteritems(transactional_doctypes)
    ]

    if not transactional_doctypes:
        return
    client = FrappeClient(conf.master_node, conf.master_user, conf.master_pass)
    clusters = client.get_list('Cluster Configuration', fields=['site_name', 'site_ip', 'user', 'password'])
    for cluster in clusters:
        for doctype, is_new, preprocess, postprocess in transactional_doctypes:
            sync_doctype(doctype, cluster, is_new, preprocess, postprocess)

def sync_doctype(doctype, cluster, is_new, preprocess, postprocess):
    site_name = cluster.get('site_name')
    if not site_name.lower().startswith('http'):
        site_name = 'http://' + site_name

    clusterclient = FrappeClient(site_name, cluster.get('user'), cluster.get('password'))
    sync_last_modified_key = "client_transaction_sync_pos_" + frappe.scrub(doctype)
    sync_queue_length = frappe.local.conf.federation_transaction_sync_queue_length or 20

    now = frappe.utils.now()

    last_sync_pos = frappe.db.sql_list('''
        SELECT
            defValue
        from
            `tabDefaultValue`
        where
            defkey=%(key)s and parent="__default"
        for update''', {
            'key': sync_last_modified_key
    })

    if not last_sync_pos:
        set_global_default(sync_last_modified_key, '')
        last_sync_pos = ''
    else:
        last_sync_pos = last_sync_pos[0]

    doc_list = clusterclient.get_list(doctype, filters=[
        [doctype, 'modified', '>', last_sync_pos],
        [doctype, 'modified', '<=', now],
    ], limit_page_length=sync_queue_length, fields=['name', 'modified'])
    if not doc_list:
        return

    max_modified = max(doc.get('modified') for doc in doc_list)

    for doc in doc_list:
        remote_doc = clusterclient.get_doc(doctype, doc.get('name'))
        remote_doc['doctype'] = doctype
        local_doc = frappe.get_doc(remote_doc)
        if not is_new(local_doc):
            continue
        preprocess(local_doc)
        local_doc.insert(ignore_permissions=True)
        postprocess(local_doc)

    set_global_default(sync_last_modified_key, max_modified)
