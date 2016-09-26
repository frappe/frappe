frappe.ui.form.on("System Settings", "refresh", function(frm) {
	frappe.setup_language_field(frm);
	frappe.call({
		method: "frappe.core.doctype.system_settings.system_settings.load",
		callback: function(data) {
			frappe.all_timezones = data.message.timezones;
			frm.set_df_property("time_zone", "options", frappe.all_timezones);

			$.each(data.message.defaults, function(key, val) {
				frm.set_value(key, val);
				sys_defaults[key] = val;
			})
		}
	});
});

