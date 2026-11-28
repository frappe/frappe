// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Provider", {
	refresh(frm) {
		// the list suggests: any provider LiteLLM knows is accepted
		frm.fields_dict.provider.df.ignore_validation = true;
	},
});
