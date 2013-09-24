cur_frm.cscript.onload = function(doc) {
	cur_frm.fields_dict.user.get_query = function() {
		return {
			query: "core.doctype.communication.communication.get_user"
		}
	};
	
	cur_frm.fields_dict.lead.get_query = function() {
		return {
			query: "core.doctype.communication.communication.get_lead"
		}
	};
	
	cur_frm.fields_dict.customer.get_query = function(doc,cdt,cdn) {
		return {	query:"controllers.queries.customer_query" } }

	cur_frm.fields_dict.supplier.get_query = function(doc,cdt,cdn) {
		return { query:"controllers.queries.supplier_query" } }
	
	if(doc.content)
		doc.content = wn.utils.remove_script_and_style(doc.content);
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
	}
}

cur_frm.cscript.contact = function(doc, dt, dn) {
	if (doc.contact) {
		return wn.call({
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