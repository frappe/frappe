// Business modules registered by apps. See frappe/utils/business_modules.py.
frappe.business_modules = {
	// Names of all registered modules, for example ["Stock", "POS"].
	get_names() {
		return (frappe.boot.business_modules || []).map((m) => m.module);
	},

	// Options for the "Business Module" Select field: blank first, then every module.
	get_select_options() {
		return [""].concat(this.get_names()).join("\n");
	},
};
