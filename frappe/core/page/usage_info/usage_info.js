frappe.pages['usage-info'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Usage Info',
		single_column: true
	});

	frappe.call({
		method: "frappe.limits.get_usage_info",
		callback: function(r) {
			var usage_info = r.message;
			if (!usage_info) {
				// nothing to show
				// TODO improve this
				return;
			}

			$(frappe.render_template("usage_info", usage_info)).appendTo(page.main);

			var btn_text = usage_info.limits.users == 1 ? __("Upgrade") : __("Renew / Upgrade");
			$(page.main).find('.btn-primary').html(btn_text).on('click', () => {
				window.open(usage_info.upgrade_url);
			});
		}
	});

}
