frappe.provide('frappe.locals.modules');

frappe.locals.modules.utils = {
	get_enabled_modules: function() {
		frappe.call({
			method: 'frappe.core.doctype.module_def.module_def.get_enabled_modules',
			callback: (r) => {
				if (r && r.message) {
					frappe.locals.modules.enabled_modules = $.extend([], r.message);
				}
			}
		})
	}
}