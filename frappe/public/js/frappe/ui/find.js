frappe.find = {
	page_primary_action: () => {
		return $('.page-actions:visible .btn-primary');
	},
	field: (fieldname, value) => {
		return new Promise(resolve => {
			let input = $(`[data-fieldname="${fieldname}"] :input`);
			if(value) {
				input.val(value).trigger('change');
				frappe.after_ajax(() => { resolve(input); });
			} else {
				resolve(input);
			}
		});
	}
};