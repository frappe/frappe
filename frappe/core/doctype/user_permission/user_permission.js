// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('User Permission', {
	setup: frm => {
		frm.set_query("allow", () => {
			return {
				"filters": {
					issingle: 0,
					istable: 0
				}
			};
		});
	},

	refresh: frm => {
		frm.add_custom_button(__('View Permitted Documents'),
			() => frappe.set_route('query-report', 'Permitted Documents For User',
				{ user: frm.doc.user }));
		frm.trigger('set_help');
	},

	allow: frm => {
		frm.trigger('set_help');
		if(frm.doc.for_value) {
			cur_frm.fields_dict.for_value.set_input(null);
		}
	},

	set_help: frm => {
		const help_wrapper = frm.fields_dict.linked_doctypes.$wrapper;
		help_wrapper.empty();
		if (frm.doc.allow) {
			frappe.call({
				method: "frappe.desk.form.linked_with.get_linked_doctypes",
				args: {
					doctype: frm.doc.allow
				},
				callback: (r) => {
					const linked_doctypes = r.message;
					if (linked_doctypes) {
						$(frappe.render_template("user_permission_help", { linked_doctypes: linked_doctypes }))
							.appendTo(help_wrapper);
					}
				}
			});
		}
	}

});
