// Business modules registered by apps. See frappe/utils/business_modules.py.
frappe.business_modules = {
	get_names() {
		return (frappe.boot.business_modules || []).map((m) => m.module);
	},

	get_select_options() {
		return [""].concat(this.get_names()).join("\n");
	},
};
