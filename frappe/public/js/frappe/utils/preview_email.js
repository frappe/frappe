frappe.preview_email = function(template, args, header) {
	frappe.call({
		method: 'frappe.email.email_body.get_email_html',
		args: {
			subject: 'Test',
			template,
			args,
			header
		}
	}).then((r) => {
		var html = r.message;
		html = html.replace(/embed=/, 'src=');
		var d = frappe.msgprint(html);
		d.$wrapper.find('.modal-dialog').css('width', '70%');
	});
};
