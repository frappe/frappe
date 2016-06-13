frappe.pages['usage-info'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Usage Info',
		single_column: true
	});

	frappe.call({
		method: "frappe.limits.get_limits",
		callback: function(r) {
			var doc = r.message;
			if(!doc.database_size) doc.database_size = 26;
			if(!doc.files_size) doc.files_size = 1;
			if(!doc.backup_size) doc.backup_size = 1;

			doc.max = flt(doc.space_limit * 1024);
			doc.total = (doc.database_size + doc.files_size + doc.backup_size);
			doc.users = keys(frappe.boot.user_info).length - 2;
			doc.today = frappe.datetime.get_today()
			doc.total_days = frappe.datetime.get_day_diff(doc.expiry, doc.creation)
			doc.used_days = frappe.datetime.get_day_diff(doc.today, doc.creation)

			$(frappe.render_template("usage_info", doc)).appendTo(page.main);

		var btn_text = doc.user_limit == 1 ? __("Upgrade") : __("Renew / Upgrade");

		if(doc.limits_upgrade_link) {
			page.set_primary_action(btn_text, function() {
				frappe.set_route("upgrade");
			});
		}
		}
	});

}
