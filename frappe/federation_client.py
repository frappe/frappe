import frappe
from frappe.frappeclient import FrappeClient
from frappe.defaults import set_global_default
from six import string_types, iteritems

def get_remote_logs():
    last_inserted_logid = frappe.db.sql("""SELECT MAX(name) FROM `tabFederation Master Log`""")[0][0]
    master_setup = FrappeClient(frappe.local.conf.federation_master_hostname,frappe.local.conf.federation_master_user, frappe.local.conf.federation_master_password)
    master_setup.post_request({
        "cmd": "frappe.federation_master.send_new_logs",
        "name_threshold": last_inserted_logid
    })

def chain_all(fns):
    if not fns:
        return (lambda *args: True)

    chain = []
    for fn in fns:
        if isinstance(fn, string_types):
            fn = frappe.get_attr(fn)
        chain.append(fn)

    def chained_fn(_, doc):
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
    print('transaction_doctypes =', transactional_doctypes)
    transactional_doctypes = [
        (dt, chain_all(value.get('is_new')), chain_all(value.get('preprocess')), chain_all(value.get('postprocess')))
            for dt, value in iteritems(transactional_doctypes)
    ]
    print('transaction_doctypes =', transactional_doctypes)

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

    print('last_sync_pos=', last_sync_pos)
    doc_list = clusterclient.get_list(doctype, filters={
        'modified': ('>', last_sync_pos),
        'modified': ('<=', now),
    }, limit_page_length=sync_queue_length, fields=['name', 'modified'])
    if not doc_list:
        print('No Items to sync')
        return
    max_modified = max(doc.get('modified') for doc in doc_list)

    for doc in doc_list:
        remote_doc = client.get_doc(doctype, doc.get(name))
        remote_doc['doctype'] = doctype
        local_doc = frappe.get_doc(doc)
        if not is_new(local_doc):
            continue
        preprocess(local_doc)
        local_doc.insert(ignore_permissions=True)
        postprocess(local_doc)

    set_global_default(sync_last_modified_key, max_modified)
