frappe.ui.form.on("System Settings", "refresh", function(frm) {
	frappe.call({
		method: "frappe.core.doctype.system_settings.system_settings.load",
		callback: function(data) {
			frappe.all_timezones = data.message.timezones;
			frappe.languages = data.message.languages;
			frm.set_df_property("time_zone", "options", frappe.all_timezones);
			frm.set_df_property("language", "options", frappe.languages);

			$.each(data.message.defaults, function(key, val) {
				frm.set_value(key, val);
				sys_defaults[key] = val;
			})
		}
	});
});

