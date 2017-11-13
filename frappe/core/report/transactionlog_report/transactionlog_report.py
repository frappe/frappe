# Copyright (c) 2013, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from  frappe import msgprint, _
from frappe.utils import now, cint

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

def sales_invoice():

    sales_invoice_data = frappe.db.sql("""Select * from tabTransactionLog trl
                left join `tabSales Invoice` si
                on trl.document_name = si.name 
                ORDER BY trl.creation""", as_dict=1)

    result = []
    remark = ''
    minus = 0

    for salinv in sales_invoice_data:
        if salinv.reference_doctype == 'Sales Invoice':
            index = getcurrentindex()
            status = 0
            minus += 1
            previous_hash = frappe.db.sql("SELECT chaining_hash FROM `tabTransactionLog` WHERE row_index = {0}".format(index - minus))
            if previous_hash:
                remark = doc_check(salinv.reference_doctype, salinv.document_name, previous_hash)

            row = [remark, salinv.creation, salinv.owner, salinv.modified_by, salinv.document_name ,salinv.reference_doctype,
                   salinv.customer_name, salinv.base_total, salinv.company, salinv.posting_date, salinv.currency,
                   salinv.company_address, salinv.paid_amount, salinv.net_total, salinv.status]

            result.append(row)

    return result


def payment_entry():

    payment_entry_data = frappe.db.sql("""SELECT * from tabTransactionLog trl
                    left join `tabPayment Entry` pe
                    on trl.document_name = pe.name
                    ORDER BY trl.creation""", as_dict=1)

    result = []
    remark = ''
    minus = 0
    for ped in payment_entry_data:
        if ped.reference_doctype == 'Payment Entry':
            status = 0
            minus += 1
            index = getcurrentindex()
            previous_hash = frappe.db.sql("SELECT chaining_hash FROM `tabTransactionLog` WHERE row_index = {0}".format(index - minus))
            if previous_hash:
                remark = doc_check(ped.reference_doctype, ped.document_name, previous_hash)

            row = [remark, ped.creation, ped.owner, ped.modified_by, ped.document_name,
                   ped.reference_doctype,ped.customer_name, ped.base_paid_amount, ped.company, ped.posting_date,
                   ped.currency,ped.company_address, ped.base_received_amount, ped.net_total, ped.payment_type]

            result.append(row)

    return result


def full_data():

    f_data = frappe.db.sql("SELECT * FROM tabTransactionLog order by creation desc ", as_dict=1)
    result = []
    remark = ''
    minus = 0
    for fd in f_data:
        data = fd.data.split()
        index = getcurrentindex()
        status = 0
        minus += 1
        previous_hash = frappe.db.sql("SELECT chaining_hash FROM `tabTransactionLog` WHERE row_index = {0}".format(index - minus))
        if previous_hash:
            remark = doc_check(fd.reference_doctype, fd.document_name, previous_hash)



        if fd.reference_doctype == 'Sales Invoice':
            row = [remark, fd.creation, fd.owner, fd.modified_by, fd.document_name, fd.reference_doctype,
                   data[60], data[01], data[51], data[34], data[10], data[20], data[38], data[12], data[22]]
        else:
            list = [data[79], data[9], data[63], data[52], data[07], data[58], data[03]]
            row = [ remark, fd.creation, fd.owner, fd.modified_by, fd.document_name, fd.reference_doctype,
                    data[79].split("'")[1], data[9], data[63], data[52], data[07], '', data[58], '', data[03]  ]
        # list[0].split("'")[1]
        # row = [remarks, fd.creation, fd.owner, fd.modified_by, fd.document_name,
        #        fd.reference_doctype,
        # data[62],data[01], data[52], data[34], data[10], data[20], data[38], data[12], data[22]
        #        fd.customer_name, fd.base_total, fd.company, fd.posting_date, fd.currency,
        #        fd.company_address, fd.paid_amount, fd.net_total, fd.status]

        result.append(row)

    return result

def getcurrentindex():
    current = frappe.db.sql("SELECT `current` FROM tabSeries WHERE name='TRANSACTLOG' FOR UPDATE")
    if current and current[0][0] is not None:
        current = current[0][0]

    return current

def doc_check(reference_doctype, doc_name, previous_hash):

    remarks = hash_check(previous_hash)
    if reference_doctype == 'Sales Invoice':
        s_invoice = frappe.db.sql("""Select si.name from tabTransactionLog trl, `tabSales Invoice` si
            	      where trl.document_name = si.name
            	      ORDER BY trl.creation desc""", as_dict=1)
        for s_inv in s_invoice:
            if doc_name in s_inv.name:
                remarks = 'Chaining successful'
                break
            else:
                remarks = 'Document missing'
    else:
        p_entry = frappe.db.sql("""SELECT pe.name from tabTransactionLog trl, `tabPayment Entry` pe
                      where trl.document_name = pe.name
                      ORDER BY trl.creation desc """, as_dict=1)
        for p_ent in p_entry:
            if doc_name in p_ent.name:
                remarks = 'Chaining successful'
                break
            else:
                remarks = 'Document missing'

    return remarks

def hash_check(previous_hash):

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


def getColumn():
    columns = [
        _("Remarks") + "::180",_("Creation") + "::150",_("Owner") + "::100",_("Modified By") + "::100", _("Document Name") + "::100",
         _("Reference Doctype") + "::150", _("Customer Name") + "::100",_("Base Total") + "::100",
        _("Company") + "::100",_("Posting Date") + "::100",_("Currency") + "::100", _("Company Address") + "::180",
        _("Paid Amount") + "::100", _("Net Total") + "::100", _("Status") + "::100"
    ]
    return columns
