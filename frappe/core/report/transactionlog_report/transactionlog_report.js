// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["TransactionLog Report"] = {
	"filters": [
		{
            'fieldname':'transaction_type',
            'label': 'Transaction Type',
            'fieldtype': 'Select',
            'options': 'Full\nSales\nPayments',
            'reqd':1
		}

	]
};
