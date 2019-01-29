// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("Website Slideshow", {
	refresh: (frm) => {
		let intro = frm.doc.__islocal?
			__("First set the name and save the record.") : __("Attach files / urls and add in table.");
		frm.set_intro(intro);

		if (frm.is_new()) return;

		frm.add_custom_button(__('Fetch attached images from document'), () => {
			const d = new frappe.ui.Dialog({
				title: __('Fetch Images'),
				fields: [
					{
						label: __('DocType'),
						fieldtype: 'Link',
						fieldname: 'reference_doctype',
						options: 'DocType',
						reqd: 1
					},
					{
						label: __('Name'),
						fieldtype: 'Dynamic Link',
						fieldname: 'reference_name',
						options: 'reference_doctype',
						reqd: 1
					}
				],
				primary_action_label: __('Add to table'),
				primary_action: ({ reference_doctype, reference_name }) => {
					frappe.db.get_list('File', {
						fields: ['file_url'],
						filters: {
							attached_to_doctype: reference_doctype,
							attached_to_name: reference_name
						}
					}).then(images => {
						frm.doc.slideshow_items = frm.doc.slideshow_items || [];
						images.forEach(image => {
							frm.doc.slideshow_items.push({
								image: image.file_url
							});
						});

						frm.refresh_field('slideshow_items');
						d.hide();
					});
				}
			});

			d.show();
		})
	}
})