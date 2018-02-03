frappe.provide("frappe.integration_service");

frappe.integration_service.gsuite = {
	create_gsuite_file: function(args, opts) {
		return frappe.call({
			type:'POST',
			method: 'frappe.integrations.doctype.gsuite_templates.gsuite_templates.create_gsuite_doc',
			args: args,
			callback: function(r) {
				var attachment = r.message;
				opts.callback && opts.callback(attachment, r);
			}
		});
	}
};
