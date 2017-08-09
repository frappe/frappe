# Overriding Link Query By Custom Script

You can override the standard link query by using `set_query`

### 1. Adding Fitlers

You can add filters to the query:

	frappe.ui.form.on("Bank Reconciliation", "onload", function(frm) {
		cur_frm.set_query("bank_account", function() {
			return {
				"filters": {
					"account_type": "Bank",
					"group_or_ledger": "Ledger"
				}
			};
		});
	});

A more complex query:

	frappe.ui.form.on("Bank Reconciliation", "onload", function(frm){
		cur_frm.set_query("bank_account", function(){
			return {
				"filters": [
					["Bank Account": "account_type", "=", "Bank"],
                                ["Bank Account": "group_or_ledger", "!=", "Group"]
				]
			}
		});
	});

---

### 2. Calling a Different Method to Generate Results

You can also set a server side method to be called on the query:

	frm.set_query("item_code", "items", function() {
		return {
			query: "erpnext.controllers.queries.item_query",
			filters: frm.doc.enquiry_type === "Maintenance" ?
				{"is_service_item": "Yes"} : {"is_sales_item": "Yes"}
		};
	});



#### Custom Method

The custom method should return a list of items for auto select. If you want to send additional data, you can send multiple columns in the list.

Parameters to the custom method are:

`def custom_query(doctype, txt, searchfield, start, page_len, filters)`

**Example:**

	# searches for leads which are not converted
	def lead_query(doctype, txt, searchfield, start, page_len, filters):
		return frappe.db.sql("""select name, lead_name, company_name from `tabLead`
			where docstatus &lt; 2
				and ifnull(status, '') != 'Converted'
				and ({key} like %(txt)s
					or lead_name like %(txt)s
					or company_name like %(txt)s)
				{mcond}
			order by
				if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
				if(locate(%(_txt)s, lead_name), locate(%(_txt)s, lead_name), 99999),
				if(locate(%(_txt)s, company_name), locate(%(_txt)s, company_name), 99999),
				name, lead_name
			limit %(start)s, %(page_len)s""".format(**{
				'key': searchfield,
				'mcond':get_match_cond(doctype)
			}), {
				'txt': "%%%s%%" % txt,
				'_txt': txt.replace("%", ""),
				'start': start,
				'page_len': page_len
			})



For more examples see:

[https://github.com/frappe/erpnext/blob/develop/erpnext/controllers/queries.py](https://github.com/frappe/erpnext/blob/develop/erpnext/controllers/queries.py)

<!-- markdown -->