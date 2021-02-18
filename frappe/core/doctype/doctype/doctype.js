// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on('DocType', {
	refresh: function(frm) {
		if(frappe.session.user !== "Administrator" || !frappe.boot.developer_mode) {
			if(frm.is_new()) {
				frm.set_value("custom", 1);
			}
			frm.toggle_enable("custom", 0);
			frm.toggle_enable("beta", 0);
		}

		if (!frm.is_new() && !frm.doc.istable) {
			if (frm.doc.issingle) {
				frm.add_custom_button(__('Go to {0}', [frm.doc.name]), () => {
					window.open(`/app/${frappe.router.slug(frm.doc.name)}`);
				});
			} else {
				frm.add_custom_button(__('Go to {0} List', [frm.doc.name]), () => {
					window.open(`/app/${frappe.router.slug(frm.doc.name)}`);
				});
			}
		}

		if(!frappe.boot.developer_mode && !frm.doc.custom) {
			// make the document read-only
			frm.set_read_only();
		}

		if(frm.is_new()) {
			if (!(frm.doc.permissions && frm.doc.permissions.length)) {
				frm.add_child('permissions', {role: 'System Manager'});
			}
		} else {
			frm.toggle_enable("engine", 0);
		}

		// set label for "In List View" for child tables
		frm.get_docfield('fields', 'in_list_view').label = frm.doc.istable ?
			__('In Grid View') : __('In List View');

		frm.events.autoname(frm);
	},

	before_save: function(frm) {
		frappe.flags.reload_bootinfo = frm.is_new();
	},

	after_save: function(frm) {
		if (frappe.flags.reload_bootinfo) {
			frappe.call({
				method: "frappe.boot.get_bootinfo",
				freeze: true,
				freeze_message: __("Reloading...")
			}).then(r => {
				if (r.message) {
					frappe.boot = r.message;
					frappe.flags.reload_bootinfo = false;
				}
			});
		}
	},

	autoname: function(frm) {
		frm.set_df_property('fields', 'reqd', frm.doc.autoname !== 'Prompt');
	}

});
