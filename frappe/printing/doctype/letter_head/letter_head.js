// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Letter Head', {
	refresh: function(frm) {
		frm.flag_public_attachments = true;
		frm.fields_dict.add_image.onclick = () => {
			let options = {
				allow_multiple: false,
				doctype: frm.doctype,
				docname: frm.docname,
				restrictions: {
					allowed_file_types: ['image/*']
				},
				on_success: file => {
					let footer_html = frm.fields_dict.footer.value || '';
					frm.set_value('footer', footer_html + `<img src="${file.file_url}" alt="">`);
				}
			};
			let file_uploader = new frappe.ui.FileUploader(options);
		}
	}
});