# Copyright (c) 2013, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from  frappe import msgprint, _
from frappe.utils import now, cint
import hashlib

def execute(filters=None):
    columns, data = [], []

    columns = getColumn()
    data = getData(filters)

    return columns, data


def getData(filters=None):

    if filters.transaction_type == 'Sales':
        si = sales_invoice()
        return si
    elif filters.transaction_type == 'Payments':
        pe = payment_entry()
        return pe
    else:
        full = full_data()
        return full


def sales_invoice(): #function to get Sales invoice data

    sales_invoice_data = frappe.db.sql("""Select * from tabTransactionLog trl
                left join `tabSales Invoice` si
                on trl.document_name = si.name 
                ORDER BY trl.creation""", as_dict=1)

    result = []
    remark = ''
    for salinv in sales_invoice_data:
        if salinv.reference_doctype == 'Sales Invoice':
            row_index = int(salinv.row_index)
            if row_index > 1:
                row_index = int(salinv.row_index) - 1

            previous_hash = frappe.db.sql("SELECT chaining_hash FROM `tabTransactionLog` WHERE row_index = {0}".format(row_index))
            remark = doc_check(salinv.reference_doctype, salinv.document_name, previous_hash)

            if remark[0] == 'Previous Document Missing':
                if remark[1]:
                    remark = remark[0]

            row = [remark, salinv.creation, salinv.owner, salinv.modified_by, salinv.document_name ,salinv.reference_doctype,
                   salinv.customer_name, salinv.base_total, salinv.company, salinv.posting_date, salinv.currency,
                   salinv.address_display, salinv.paid_amount, salinv.net_total, salinv.status]

            result.append(row)
    return result


def payment_entry(): #function to Payment entry data

    payment_entry_data = frappe.db.sql("""SELECT * from tabTransactionLog trl
                    left join `tabPayment Entry` pe
                    on trl.document_name = pe.name
                    ORDER BY trl.creation""", as_dict=1)

    result = []
    remark = ''
    for ped in payment_entry_data:
        if ped.reference_doctype == 'Payment Entry':
            row_index = int(ped.row_index)
            if row_index > 1:
                row_index = int(ped.row_index) - 1

            previous_hash = frappe.db.sql("SELECT chaining_hash FROM `tabTransactionLog` WHERE row_index = {0}".format(row_index))
            remark = doc_check(ped.reference_doctype, ped.document_name, previous_hash)
            if remark[0] == 'Previous Document Missing':
                if remark[1]:
                    remark = remark[0]
            row = [remark, ped.creation, ped.owner, ped.modified_by, ped.document_name,
                   ped.reference_doctype,ped.party, ped.base_paid_amount, ped.company, ped.posting_date,
                   ped.paid_from_account_currency, ped.company_address, ped.base_received_amount, ped.base_total_allocated_amount, ped.payment_type]

            result.append(row)
    return result


def full_data(): #function to get the Full data

    f_data = frappe.db.sql("SELECT * FROM tabTransactionLog order by creation desc ", as_dict=1)
    result = []
    remark = ''
    for fd in f_data:
        data = json.loads(fd.data)
        row_index = int(fd.row_index)
        if row_index > 1:
            row_index = int(fd.row_index) - 1

        previous_hash = frappe.db.sql("SELECT chaining_hash FROM `tabTransactionLog` WHERE row_index = {0}".format(row_index))
        remark = doc_check(fd.reference_doctype, fd.document_name, previous_hash)
        if remark[0] == 'Previous Document Missing':
            if remark[1]:
                remark = remark[0]

        if fd.reference_doctype == 'Sales Invoice':
            s_invoice = frappe.db.sql("SELECT status, base_paid_amount FROM `tabSales Invoice` where name= '{0}' ".format(fd.document_name),as_dict=1)
            if s_invoice:
                paid_amount = s_invoice[0].base_paid_amount
                status = s_invoice[0].status
            else:
                paid_amount = 0
                status = 'Unpaid'
            row = [remark, fd.creation, fd.owner, fd.modified_by, fd.document_name, fd.reference_doctype,
                   data['self.customer'], data['self.base_net_total'], data['self.company'],
                   data['self.posting_date'], data['self.company_currency'],
                   data['self.company_address'], paid_amount, data['self.net_total'], status ]
        else:
            row = [ remark, fd.creation, fd.owner, fd.modified_by, fd.document_name, fd.reference_doctype,
                    data['self.party_name'], data['self.base_paid_amount'], data['self.company'],
                    data['self.posting_date'], data['self.company_currency'], '',
                    data['self.paid_amount'], data['self.total_allocated_amount'], data['self.payment_type'] ]

        result.append(row)
    return result


def doc_check(reference_doctype, doc_name, previous_hash): #Main function to check the document integrity

    remarks = ''
    if previous_hash:
        remarks = hash_check(previous_hash)
        if reference_doctype == 'Sales Invoice':
            s_invoice = frappe.db.sql("""Select si.name from tabTransactionLog trl, `tabSales Invoice` si
                          where trl.document_name = si.name
                          ORDER BY trl.creation desc""", as_dict=1)
            if s_invoice:
                for s_inv in s_invoice:
                    if doc_name in s_inv.name:
                        remarks = 'Chaining successful'
                        break
                    else:
                        remarks = 'Document missing'
            else:
                remarks = 'Document Missing'
        else:
            p_entry = frappe.db.sql("""SELECT pe.name from tabTransactionLog trl, `tabPayment Entry` pe
                          where trl.document_name = pe.name
                          ORDER BY trl.creation desc """, as_dict=1)
            if p_entry:
                for p_ent in p_entry:
                    if doc_name in p_ent.name:
                        remarks = 'Chaining successful'
                        break
                    else:
                        remarks = 'Document missing'
            else:
                remarks = 'Document Missing'
    else:
        remarks = integrity_chain()

    return remarks


def hash_check(previous_hash): #function for comparing the previous and current chain hash

    remarks = ''
    status = 0
    chain = frappe.db.sql("SELECT chaining_hash FROM tabTransactionLog order by creation desc ", as_dict=1)
    for ch in chain:
        if previous_hash[0][0] in ch.chaining_hash:
            status = 1

    if status == 1:
        remarks = 'Chaining successful'
    else:
        remarks = 'Chaining Broked or altered'

    return remarks


def integrity_chain(): #function to check the chain integrity

    f_data = frappe.db.sql("SELECT group_concat(row_index) as index_list "
                           "FROM tabTransactionLog order by creation desc ", as_dict=1)

    current_index = getcurrentindex()
    missing_index_list = missing_elements(f_data[0].index_list, current_index)
    if missing_index_list:
        remarks = ''
        a = hash_chain(missing_index_list)
        for match_hash_list in a:
            if match_hash_list[0] != match_hash_list[1]:
                remarks = 'Previous Document Missing'
        return remarks, missing_index_list


def getcurrentindex():  #function for getting current index from tabseries
    current = frappe.db.sql("SELECT `current` FROM tabSeries WHERE name='TRANSACTLOG' ")
    if current and current[0][0] is not None:
         current = current[0][0]
    return current


def missing_elements(L, end): #function for getting missing indexes
    l = eval(L)
    start = l[0]
    # start, end = l[0], l[-1]
    return sorted(set(range(start, end + 1)).difference(l))


def hash_chain(missing_index_list): #function created for generating and comparing the chain hash

    # Code written to regenerate chain_hash
    row = []
    result = []
    chaining_hash = ''
    transaction_hash = ''
    result_hash = ''
    sha = hashlib.sha256()
    for m in missing_index_list:
        m_index = m-1
        sql = """SELECT name, transaction_hash, chaining_hash, previous_hash, reference_doctype FROM tabTransactionLog where row_index = {0}
                             order by creation""".format(m_index)
        query_data = frappe.db.sql(sql,as_dict = 1)
        if query_data:
            transaction_hash = query_data[0].transaction_hash
            previous_hash = query_data[0].previous_hash
            sha.update(str(transaction_hash) + str(previous_hash))
            result_hash = sha.hexdigest()

    #Code written to get next chain hash
        m_index += 2
        query_data2 = frappe.db.sql("SELECT name, transaction_hash, chaining_hash, previous_hash, reference_doctype FROM tabTransactionLog "
                                    "where row_index = {0} order by creation".format(m_index), as_dict = 1)
        if query_data2:
            chaining_hash = query_data2[0].chaining_hash

        row = [result_hash, chaining_hash]
        result.append(row)

    return result


def getColumn():
    columns = [
        _("Remarks") + "::180",_("Creation") + "::150",_("Owner") + "::100",_("Modified By") + "::100", _("Document Name") + "::130",
         _("Reference Doctype") + "::150", _("Customer Name") + "::150",_("Base Total") + "::100",
        _("Company") + "::100",_("Posting Date") + "::100",_("Currency") + "::100", _("Company Address") + "::180",
        _("Paid Amount") + "::100", _("Net Total") + "::100", _("Status") + "::100"
    ]
    return columns
