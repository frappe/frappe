frappe.listview_settings['Email Queue'] = {
	get_indicator: function(doc) {
		var colour = {'Sent': 'green', 'Sending': 'blue', 'Not Sent': 'grey', 'Error': 'red', 'Expired': 'orange'};
		return [__(doc.status), colour[doc.status], "status,=," + doc.status];
	},
<<<<<<< HEAD
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
=======
	refresh: show_toggle_sending_button,
	onload: function(list_view) {
		frappe.require("logtypes.bundle.js", () => {
			frappe.utils.logtypes.show_log_retention_message(list_view.doctype);
		})
>>>>>>> 9a7f92ca1d (fix!: allow system managers to toggle email queue)
	}
};

function show_toggle_sending_button(list_view) {
	if (!has_common(frappe.user_roles, ["Administrator", "System Manager"]))
		return;

	const sending_disabled = cint(frappe.sys_defaults.suspend_email_queue);
	const label = sending_disabled ? __("Resume Sending") : __("Suspend Sending");

	list_view.page.add_inner_button(
		label,
		async () => {
			await frappe.xcall(
				"frappe.email.doctype.email_queue.email_queue.toggle_sending",

				// enable if disabled
				{enable: sending_disabled}
			);

			// set new value for suspend_email_queue in sys_defaults
			frappe.sys_defaults.suspend_email_queue = sending_disabled ? 0 : 1;

			// clear the button and show one with the opposite label
			list_view.page.remove_inner_button(label);
			show_toggle_sending_button(list_view);
		}
	);
}