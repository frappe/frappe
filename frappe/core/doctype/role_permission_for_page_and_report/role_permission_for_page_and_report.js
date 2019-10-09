// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Role Permission for Page and Report', {
	setup: function(frm) {
		frm.trigger("set_queries")
	},

	refresh: function(frm) {
		frm.disable_save();
		frm.role_area.hide();
		frm.events.add_custom_buttons(frm);
	},

	add_custom_buttons: function(frm) {
		frm.clear_custom_buttons();
		if(frm.doc.set_role_for && frm.doc[frappe.model.scrub(frm.doc.set_role_for)]) {
			frm.add_custom_button(__("Reset to defaults"), function() {
				frm.trigger("reset_roles");
			});

			frm.add_custom_button(__("Update"), function() {
				frm.trigger("update_report_page_data");
			}).addClass('btn-primary');
		}
	},

	onload: function(frm) {
		if(!frm.roles_editor) {
			frm.role_area = $('<div style="min-height: 300px">')
				.appendTo(frm.fields_dict.roles_html.wrapper);
			frm.roles_editor = new frappe.RoleEditor(frm.role_area, frm);
		}
	},

	set_queries: function(frm) {
		frm.set_query("page", function() {
			return {
				filters: {
					system_page: 0
				}
			}
		});
	},

	set_role_for: function(frm) {
		frm.trigger("clear_fields")
		frm.toggle_display('roles_html', false)
	},

	clear_fields: function(frm) {
		var field = (frm.doc.set_role_for == 'Report') ? 'page' : 'report';
		frm.set_value(field, '');
	},

	page: function(frm) {
		frm.events.add_custom_buttons(frm);
		if(frm.doc.page) {
			frm.trigger("set_report_page_data");
		} else {
			frm.trigger("set_role_for");
		}
	},

	report: function(frm){
		frm.events.add_custom_buttons(frm);
		if(frm.doc.report) {
			frm.trigger("set_report_page_data");
		} else {
			frm.trigger("set_role_for");
		}
	},

	set_report_page_data: function(frm) {
		frm.toggle_display('roles_html', true)
		frm.role_area.show();

		return frm.call({
			method:"set_report_page_data",
			doc: frm.doc,
			callback: function(r) {
				refresh_field('roles')
				frm.roles_editor.show()
			}
		})
	},

	update_report_page_data: function(frm) {
		frm.trigger("validate_mandatory_fields")
		if(frm.roles_editor) {
			frm.roles_editor.set_roles_in_table()
		}

		return frm.call({
			method:"update_report_page_data",
			doc: frm.doc,
			callback: function(r) {
				refresh_field('roles')
				frm.roles_editor.show()
				frappe.msgprint(__("Successfully Updated"))
			}
		})
	},

	reset_roles: function(frm) {
		frm.trigger("validate_mandatory_fields")
		return frm.call({
			method:"reset_roles",
			doc: frm.doc,
			callback: function(r) {
				refresh_field('roles')
				frm.roles_editor.show()
				frappe.msgprint(__("Successfully Updated"))
			}
		})
	},

	validate_mandatory_fields: function(frm) {
		if(!frm.doc.set_role_for){
			frappe.throw(__("Mandatory field: set role for"))
		}

		if(frm.doc.set_role_for && !frm.doc[frm.doc.set_role_for.toLocaleLowerCase()]) {
			frappe.throw(__("Mandatory field: {0}", [frm.doc.set_role_for]))
		}
	}
});
