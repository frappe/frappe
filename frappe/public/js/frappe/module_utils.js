frappe.provide('frappe.enabled_modules');

frappe.enabled_modules.utils = {
	get_enabled_modules: function() {
		frappe.call({
			method: 'frappe.core.doctype.module_def.module_def.get_enabled_modules',
			callback: (r) => {
				if (r && r.message) {
					frappe.enabled_modules.modules = $.extend([], r.message);
				}
			}
		})
	}
}