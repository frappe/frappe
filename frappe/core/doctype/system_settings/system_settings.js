frappe.ui.form.on("System Settings", "refresh", function(frm) {
	frappe.call({
		method: "frappe.core.doctype.system_settings.system_settings.load",
		callback: function(data) {
			frappe.all_timezones = data.message.timezones;
			frm.set_df_property("time_zone", "options", frappe.all_timezones);

			$.each(data.message.defaults, function(key, val) {
				frm.set_value(key, val);
				frappe.sys_defaults[key] = val;
			})
		}
	});
});

frappe.ui.form.on("System Settings", "enable_password_policy", function(frm) {
	if(frm.doc.enable_password_policy == 0){
		frm.set_value("minimum_password_score", "");
	} else {
		frm.set_value("minimum_password_score", "2");
	}
});

frappe.ui.form.on("System Settings", "enable_two_factor_auth", function(frm) {
	if(frm.doc.enable_two_factor_auth == 0){
		frm.set_value("bypass_2fa_for_retricted_ip_users", 0);
	}
});