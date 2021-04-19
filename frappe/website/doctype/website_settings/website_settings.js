frappe.ui.form.on('Website Settings', {
	setup(frm) {
		frm.set_query('navbar_template', () => ({
			filters: {
				type: 'Navbar'
			}
		}));
		frm.set_query('footer_template', () => ({
			filters: {
				type: 'Footer'
			}
		}));
	},

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
		frm.fields_dict.top_bar_items.grid.update_docfield_property(
			'parent_label', 'options', frm.events.get_parent_options(frm, "top_bar_items")
		);
	},

	set_parent_label_options_footer: function(frm) {
		frm.fields_dict.footer_items.grid.update_docfield_property(
			'parent_label', 'options', frm.events.get_parent_options(frm, "footer_items")
		);
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

	edit_navbar_template_values(frm) {
		frm.events.edit_template_values(frm, 'navbar_template');
	},

	edit_footer_template_values(frm) {
		frm.events.edit_template_values(frm, 'footer_template');
	},

	edit_template_values(frm, template_field) {
		let values_field = template_field + '_values';
		let template = frm.doc[template_field];
		if (!template) {
			frappe.show_alert(__('Please select {0}', [frm.get_docfield(template_field).label]));
			return;
		}
		let values = JSON.parse(frm.doc[values_field] || "{}");
		open_web_template_values_editor(template, values)
			.then(new_values => {
				frm.set_value(values_field, JSON.stringify(new_values));
			});
	}


});

frappe.ui.form.on('Top Bar Item', {
	top_bar_items_delete(frm) {
		frm.events.set_parent_label_options(frm);
	},

	footer_items_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, 'right', 0);
	},

	footer_items_delete(frm) {
		frm.events.set_parent_label_options_footer(frm);
	},

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
