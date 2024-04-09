frappe.provide("frappe.ui");

frappe.ui.AddressAutocompleteDialog = class AddressAutocompleteDialog {
	constructor(opts) {
		this.title = opts?.title || __("New Address");
		this.link_doctype = opts?.link_doctype;
		this.link_name = opts?.link_name;
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
						"frappe.integrations.doctype.address_autocomplete_settings.address_autocomplete_settings.autocomplete",
				},
			],
			primary_action_label: __("Save Address"),
			primary_action: () => {
				dialog.hide();
				// TODO: save the selected address to the database
			},
			secondary_action_label: __("Edit Address"),
			secondary_action: () => {
				dialog.hide();
				// TODO: open the selected address in the address form
			},
		});

		return dialog;
	}

	show() {
		this.dialog.show();
	}
};
