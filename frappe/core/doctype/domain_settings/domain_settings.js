// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Domain Settings', {
	onload: function(frm) {
		frm.fields_dict.domains.get_data = () => {
			return frappe.boot.all_domains;
		};
		frm.fields_dict.domains.refresh_input_area();
	},

	validate: function(frm) {
		frm.trigger('set_options_in_table');
	},

	set_options_in_table: function(frm) {
		let selected_options = frm.fields_dict.domains.selected_options;
		let unselected_options = frm.fields_dict.domains.options.filter(option => {
			return !selected_options.includes(option);
		});

		let existing_options_map = {};
		let existing_options_list = [];
		(frm.doc.active_domains || []).map(row => {
			existing_options_map[row.domain] = row.name;
			existing_options_list.push(row.domain);
		});

		// remove unchecked options
		unselected_options.map(option => {
			if(existing_options_list.includes(option)) {
				frappe.model.clear_doc("Has Domain", existing_options_map[option]);
			}
		});

		// add new options that are checked
		selected_options.map(option => {
			if(!existing_options_list.includes(option)) {
				frappe.model.clear_doc("Has Domain", existing_options_map[option]);
				let row = frappe.model.add_child(frm.doc, "Has Domain", "active_domains");
				row.domain = option;
			}
		});

		refresh_field('active_domains');
	}
});
