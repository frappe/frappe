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

	full = full_data()
	return full

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
		frappe.logger().debug(remark)
		if remark:
			if remark[0]== 'Previous Document Missing':
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
			if data['action'] == 'Printed':
				row = [remark, fd.creation, fd.owner, fd.modified_by, fd.document_name, data['action'],
					   fd.reference_doctype,
					   data['customer'], status, data['company'],
					   data['posting_date'], data['currency'],
					   paid_amount, data['total_taxes_and_charges'], data['base_net_total'], data['net_total']]
			else:
				row = [remark, fd.creation, fd.owner, fd.modified_by, fd.document_name, data['action'], fd.reference_doctype,
				   data['party'], status, data['company'],
				   data['posting_date'], data['account_currency'],
				   paid_amount, data['total_taxes_and_charges'], data['base_net_total'], data['net_total']]
		else:
			if data['action'] == 'Printed':
				row = [remark, fd.creation, fd.owner, fd.modified_by, fd.document_name, data['action'],
					   fd.reference_doctype, data['party'], data['payment_type'], data['company'],
					   data['posting_date'], data['paid_from_account_currency'],
					   data['paid_amount'], 0, data['total_allocated_amount'], data['paid_amount']]
			else:
				row = [remark, fd.creation, fd.owner, fd.modified_by, fd.document_name, data['action'], fd.reference_doctype,
					data['party'],data['payment_type'],  data['company'],
					data['posting_date'], data['account_currency'],
					data['paid_amount'], 0, data['total_allocated_amount'], data['paid_amount']]

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
						remarks = 'Chaining Successful'
						break
					else:
						remarks = 'Document Missing'
			else:
				remarks = 'Document Missing'
		else:
			p_entry = frappe.db.sql("""SELECT pe.name from tabTransactionLog trl, `tabPayment Entry` pe
						  where trl.document_name = pe.name
						  ORDER BY trl.creation desc """, as_dict=1)
			if p_entry:
				for p_ent in p_entry:
					if doc_name in p_ent.name:
						remarks = 'Chaining Successful'
						break
					else:
						remarks = 'Document Missing'
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
		remarks = 'Chaining Successful'
	else:
		remarks = 'Chaining Broken or Altered'

	return remarks


def integrity_chain(): #function to check the chain integrity

	f_data = frappe.db.sql("SELECT group_concat(row_index) as index_list "
						   "FROM tabTransactionLog order by creation desc ", as_dict=1)
	remarks = ''
	current_index = getcurrentindex()
	missing_index_list = missing_elements(f_data[0].index_list, current_index)
	if missing_index_list:
		a = hash_chain(missing_index_list)
		for match_hash_list in a:
			if match_hash_list[0] != match_hash_list[1]:
				remarks = 'Previous Document Missing'
	else:
		remarks = 'Previous Document Missing'

	return remarks


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
		_("Action") + "::100",_("Reference Doctype") + "::150", _("Customer Name") + "::150",_("Status") + "::100",
		_("Company") + "::100",_("Posting Date") + "::100",_("Currency") + "::100",
		_("Paid Amount") + "::100",  _("Total Taxes and Charges") + "::180", _("Base Total") + "::100", _("Net Total") + "::100"
	]
	return columns
