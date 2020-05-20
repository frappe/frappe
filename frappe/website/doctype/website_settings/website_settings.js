frappe.ui.form.on('Website Settings', {
	refresh: function(frm) {
		frm.add_custom_button(__('View Website'), () => {
			window.open('/', '_blank');
		});
	},

	set_banner_from_image: function(frm) {
		if (!frm.doc.banner_image) {
			frappe.msgprint(__("Select a Brand Image first."));
		}
		frm.set_value("brand_html", "<img src='"+ frm.doc.banner_image + "'>");
	},

	onload_post_render: function(frm) {
		frm.trigger('set_parent_label_options');
	},

	set_parent_label_options: function(frm) {
		frappe.meta.get_docfield("Top Bar Item", "parent_label", frm.docname).options =
			frm.events.get_parent_options(frm, "top_bar_items");

		if ($(frm.fields_dict.top_bar_items.grid.wrapper).find(".grid-row-open")) {
			frm.fields_dict.top_bar_items.grid.refresh();
		}
	},

	set_parent_label_options_footer: function(frm) {
		frappe.meta.get_docfield("Top Bar Item", "parent_label", frm.docname).options =
			frm.events.get_parent_options(frm, "footer_items");

		if ($(frm.fields_dict.footer_items.grid.wrapper).find(".grid-row-open")) {
			frm.fields_dict.footer_items.grid.refresh();
		}
	},

	authorize_api_indexing_access: function(frm) {
		let reauthorize = 0;
		if (frm.doc.authorization_code) {
			reauthorize = 1;
		}

		frappe.call({
			method: "frappe.website.doctype.website_settings.google_indexing.authorize_access",
			args: {
				"g_indexing": frm.doc.name,
				"reauthorize": reauthorize
			},
			callback: function(r) {
				if (!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			}
		});
	},

	enable_view_tracking: function(frm) {
		frappe.boot.website_tracking_enabled = frm.doc.enable_view_tracking;
	},

	set_parent_options: function(frm, doctype, name) {
		var item = frappe.get_doc(doctype, name);
		if(item.parentfield === "top_bar_items") {
			frm.trigger('set_parent_label_options');
		}
		else if (item.parentfield === "footer_items") {
			frm.trigger('set_parent_label_options_footer');
		}
	},

	get_parent_options: function(frm, table_field) {
		var items = frm.doc[table_field] || [];
		var main_items = [''];
		for (var i in items) {
			var d = items[i];
			if(!d.url && d.label) {
				main_items.push(d.label);
			}
		}
		return main_items.join('\n');
	},
});

frappe.ui.form.on('Top Bar Item', {
	parent_label: function(frm, doctype, name) {
		frm.events.set_parent_options(frm, doctype, name);
	},

	url: function(frm, doctype, name) {
		frm.events.set_parent_options(frm, doctype, name);
	},

	label: function(frm, doctype, name) {
		frm.events.set_parent_options(frm, doctype, name);
	},
});

frappe.tour['Website Settings'] = [
	{
		fieldname: "enable_view_tracking",
		title: __("Enable Tracking Page Views"),
		description: __("Checking this will enable tracking page views for blogs, web pages, etc."),
	},
	{
		fieldname: "disable_signup",
		title: __("Disable Signup for your site"),
		description: __("Check this if you don't want users to sign up for an account on your site. Users won't get desk access unless you explicitly provide it."),
	}
];