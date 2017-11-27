// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Domain Settings', {
	onload: function(frm) {
		frm.fields_dict.domains.get_data = () => {
			return frappe.boot.all_domains.map(domain => {
				return { label: domain, value: domain };
			});
		};
		frm.fields_dict.domains.refresh_input_area();
	},

	validate: function(frm) {
		frm.trigger('set_options_in_table');
	},

	set_options_in_table: function(frm) {
		let selected_options = frm.doc.domains;
		let unselected_options = frm.fields_dict.domains.options
			.map(option => option.value)
			.filter(value => {
				return !selected_options.includes(value);
			});

		let map = {}, list = [];
		(frm.doc.active_domains || []).map(row => {
			map[row.domain] = row.name;
			list.push(row.domain);
		});

		unselected_options.map(option => {
			if(list.includes(option)) {
				frappe.model.clear_doc("Has Domain", map[option]);
			}
		});

		selected_options.map(option => {
			if(!list.includes(option)) {
				frappe.model.clear_doc("Has Domain", map[option]);
				let row = frappe.model.add_child(frm.doc, "Has Domain", "active_domains");
				row.domain = option;
			}
		});

		refresh_field('active_domains');
	}
});
