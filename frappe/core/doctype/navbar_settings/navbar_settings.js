// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Navbar Settings", {
	refresh: function(frm) {
        frm.add_custom_button(__('Reset to default'), () => {
            frappe.confirm(
                __('This will reset the dropdown items to their default configuration in Help dropdown and User dropdown in the navbar. Do you want to continue?'),
                () => frm.call('set_items')
            )
        });
	}
});
