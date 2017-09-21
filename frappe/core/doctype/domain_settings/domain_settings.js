// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Domain Settings', {
	onload: function(frm) {
		let domains = $('<div class="domain-editor">')
			.appendTo(frm.fields_dict.domains_html.wrapper);

		if(!frm.domain_editor) {
			frm.domain_editor = new frappe.DomainsEditor(domains, frm);
		}

		frm.domain_editor.show();
	},

	validate: function(frm) {
		if(frm.domain_editor) {
			frm.domain_editor.set_items_in_table();
		}
	},
});

frappe.DomainsEditor = frappe.CheckboxEditor.extend({
	init: function(wrapper, frm) {
		var opts = {};
		$.extend(opts, {
			wrapper: wrapper,
			frm: frm,
			field_mapper: {
				child_table_field: "active_domains",
				item_field: "domain",
				cdt: "Has Domain"
			},
			attribute: 'data-domain',
			checkbox_selector: false,
			get_items: this.get_all_domains,
			editor_template: this.get_template()
		});

		this._super(opts);
	},

	get_template: function() {
		return `
			<div class="checkbox" data-domain="{{item}}">
				<label>
				<input type="checkbox">
				<span class="label-area small">{{ __(item) }}</span>
				</label>
			</div>
		`;
	},

	get_all_domains: function() {
		// return all the domains available in the system
		this.items = frappe.boot.all_domains;
		this.render_items();
	},
});