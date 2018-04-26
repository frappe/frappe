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
		frm.trigger('set_linked_doctype_multicheck');
	},

	allow: frm => {
		frm.trigger('set_linked_doctype_multicheck');
		if(frm.doc.for_value) {
			cur_frm.fields_dict.for_value.set_input(null);
		}
	},

	before_save: frm => {
		const linked_doctype_multicheck = frm.linked_doctype_multicheck.get_unchecked_options();
		frm.doc.skip_for_doctype = linked_doctype_multicheck.join('\n');
	},

	set_linked_doctype_multicheck: frm => {
		const help_wrapper = frm.fields_dict.linked_doctypes.$wrapper;
		help_wrapper.empty();
		if (frm.doc.allow) {
			frappe.call({
				method: "frappe.desk.form.linked_with.get_linked_doctypes",
				args: {
					doctype: frm.doc.allow,
					without_ignore_user_permissions_enabled: true
				},
				callback: (r) => {
					const linked_doctypes = r.message || {};
					const checked_doctypes = frm.doc.skip_for_doctype ? frm.doc.skip_for_doctype.split('\n') : [];
					let for_multicheck_options = [];
					Object.keys(linked_doctypes).forEach(doctype => {
						for_multicheck_options.push({
							label: doctype,
							value: doctype,
							checked: checked_doctypes.length ? !checked_doctypes.includes(doctype) : 1
						});
					});
					if (for_multicheck_options.length) {
						frm.linked_doctype_multicheck = frappe.ui.form.make_control({
							parent: help_wrapper,
							df: {
								'label': 'Apply User Permission for following DocType',
								'fieldname': 'next_actions_multicheck',
								'fieldtype': 'MultiCheck',
								'options': for_multicheck_options,
								'columns': 3,
								'select_all': for_multicheck_options.length > 5
							},
						});
					}
				}
			});
		}
	}

});
