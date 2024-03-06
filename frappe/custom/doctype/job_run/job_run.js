// Copyright (c) 2019, Sachin Mane and contributors
// For license information, please see license.txt

frappe.ui.form.on('Job Run', {
	refresh: function(frm) {
		frm.add_custom_button(__('Retry'), function(){
			frappe.call('latte.latte_core.doctype.job_run.job_run.retry',{'jobrun_name':cur_frm.doc.name})
		});

	}
});
