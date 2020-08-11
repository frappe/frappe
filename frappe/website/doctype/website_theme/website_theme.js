// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on('Website Theme', {
	refresh(frm) {
		frm.clear_custom_buttons();
		frm.toggle_display(["module", "custom"], !frappe.boot.developer_mode);

		frm.trigger('set_default_theme_button_and_indicator');

		if (!frm.doc.custom && !frappe.boot.developer_mode) {
			frm.set_read_only();
			frm.disable_save();
		} else {
			frm.enable_save();
		}
	},

	set_default_theme_button_and_indicator(frm) {
		frappe.db.get_single_value('Website Settings', 'website_theme')
			.then(value => {
				if (value === frm.doc.name) {
					frm.page.set_indicator(__('Default Theme'), 'green');
				} else {
					frm.page.clear_indicator();
					// show set as default button
					if (!frm.is_new() && !frm.is_dirty()) {
						frm.add_custom_button(__('Set as Default Theme'), () => {
							frm.call('set_as_default').then(() => frm.trigger('refresh'));
						});
					}
				}
			});
	}
});
