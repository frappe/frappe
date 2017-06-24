frappe.listview_settings['Email Queue'] = {
	get_indicator: function(doc) {
		var colour = {'Sent': 'green', 'Sending': 'blue', 'Not Sent': 'grey', 'Error': 'red', 'Expired': 'orange'};
		return [__(doc.status), colour[doc.status], "status,=," + doc.status];
	},
	refresh: function(doclist){
		if (has_common(frappe.user_roles, ["Administrator", "System Manager"])){
			if (cint(frappe.defaults.get_default("hold_queue"))){
				doclist.page.clear_inner_toolbar()
				doclist.page.add_inner_button(__("Resume Sending"), function() {
					frappe.defaults.set_default("hold_queue", 0);
					cur_list.refresh();
				})
			} else {
				doclist.page.clear_inner_toolbar()
				doclist.page.add_inner_button(__("Suspend Sending"), function() {
					frappe.defaults.set_default("hold_queue", 1)
					cur_list.refresh();
				})
			}
		}
	}
}
