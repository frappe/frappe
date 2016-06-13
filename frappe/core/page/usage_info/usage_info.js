frappe.pages['usage-info'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Usage Info',
		single_column: true
	});

	frappe.call({
			method: "frappe.limits.get_limits",
			callback: function(doc) {
				doc = doc.message;
				if(!doc.database_size) doc.database_size = 26;
				if(!doc.files_size) doc.files_size = 1;
				if(!doc.backup_size) doc.backup_size = 1;

				doc.max = flt(doc.space_limit * 1024);
				doc.total = (doc.database_size + doc.files_size + doc.backup_size);
				doc.users = keys(frappe.boot.user_info).length - 2;

				$(frappe.render_template("usage_info", doc)).appendTo(page.main);
		}
	});

}
