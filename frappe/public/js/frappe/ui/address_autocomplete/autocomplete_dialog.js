frappe.provide("frappe.ui");

frappe.ui.AddressAutocompleteDialog = class AddressAutocompleteDialog {
	constructor(opts) {
		this.title = opts?.title || __("New Address");
		this.link_doctype = opts?.link_doctype;
		this.link_name = opts?.link_name;
		this.after_insert = opts?.after_insert;
		this.dialog = this._get_dialog();
	}

	_get_dialog() {
		// sourcery skip: inline-immediately-returned-variable
		const dialog = new frappe.ui.Dialog({
			title: this.title,
			fields: [
				{
					fieldname: "search",
					fieldtype: "Autocomplete",
					label: __("Search"),
					reqd: 1,
					get_query:
						"frappe.integrations.doctype.geolocation_settings.geolocation_settings.autocomplete",
				},
			],
			primary_action_label: __("Save Address"),
			primary_action: () => {
				// Insert the address into the database
				dialog.hide();

				const address = this.parse_selected_value();
				address["doctype"] = "Address";
				address["links"] = [
					{
						link_doctype: this.link_doctype,
						link_name: this.link_name,
					},
				];
				frappe.db.insert(address).then((doc) => {
					this.after_insert && this.after_insert(doc);
				});
			},
			secondary_action_label: __("Edit Address"),
			secondary_action: () => {
				// Open the address in the form view
				dialog.hide();

				const address = this.parse_selected_value();
				frappe.new_doc("Address", address);
			},
		});

		return dialog;
	}

	parse_selected_value() {
		const data = this.dialog.get_values();
		return JSON.parse(data.search);
	}

	show() {
		this.dialog.show();
	}
};
