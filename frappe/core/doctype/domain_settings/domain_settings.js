// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Domain Settings', {
	before_load: function(frm) {
		frm.layout.add_fields([
			{
				fieldname: "active_domains_sb",
				fieldtype: "Section Break",
				label: __("Active Domains")
			},
			{
				fieldname: "domains",
				fieldtype: "MultiCheck",
				label: __("Active Domains"),
				get_data: () => {
					let active_domains = (frm.doc.active_domains || []).map(row => row.domain);
					return frappe.boot.all_domains.map(domain => {
						return {
							label: domain,
							value: domain,
							checked: active_domains.includes(domain)
						};
					});
				}
			}
		]);
		frm.fields_dict.domains.refresh_input();
	},

	validate: function(frm) {
		frm.trigger('set_options_in_table');
	},

	set_options_in_table: function(frm) {
		let selected_options = frm.fields_dict.domains.get_value();
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
