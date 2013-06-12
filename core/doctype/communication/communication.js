cur_frm.cscript.onload = function(doc) {
	cur_frm.fields_dict.user.get_query = function() {
		return "select name, concat_ws(' ', first_name, middle_name, last_name) \
			from `tabProfile` where ifnull(enabled, 0)=1 and docstatus < 2 and \
			(%(key)s like \"%s\" or \
			concat_ws(' ', first_name, middle_name, last_name) like \"%%%s\") \
			limit 50";
	};
	
	cur_frm.fields_dict.lead.get_query = function() {
		return "select name, lead_name from `tabLead` \
			where docstatus < 2 and \
			(%(key)s like \"%s\" or lead_name like \"%%%s\" or \
			company_name like \"%%%s\") \
			order by lead_name asc limit 50";
	};
	
	cur_frm.fields_dict.customer.get_query = erpnext.utils.customer_query;
	cur_frm.fields_dict.supplier.get_query = erpnext.utils.supplier_query;
}

cur_frm.cscript.refresh = function(doc, dt, dn) {
	if(!doc.__islocal) {
		var field_list = ['lead', 'customer', 'supplier', 'contact', 'opportunity',
			'quotation', 'support_ticket'];
		var hide_list = [];
		$.each(field_list, function(i, v) {
			if(!doc[v]) hide_list.push(v);
		});
		
		if(hide_list.length < field_list.length) hide_field(hide_list);
		
		doc.content = wn.utils.escape_script_and_style(doc.content);
	}
}

cur_frm.cscript.contact = function(doc, dt, dn) {
	if (doc.contact) {
		wn.call({
			method: 'support.doctype.communication.communication.get_customer_supplier',
			args: {
				contact: doc.contact
			},
			callback: function(r, rt) {
				if (!r.exc && r.message) {
					doc = locals[doc.doctype][doc.name];
					doc[r.message['fieldname']] = r.message['value'];
					refresh_field(r.message['fieldname']);
				}
			},
		});
	}
}