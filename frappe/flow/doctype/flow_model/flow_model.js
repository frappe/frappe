// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Model", {
	refresh(frm) {
		load_provider_models(frm);

		if (frm.is_new()) return;

		frm.add_custom_button(__("Test Connection"), async () => {
			if (frm.is_dirty()) {
				frappe.msgprint({
					title: __("Unsaved Changes"),
					message: __("Save the document before testing the connection."),
					indicator: "orange",
				});
				return;
			}

			frappe.dom.freeze(__("Testing connection…"));
			try {
				const r = await frm.call("test_connection");
				if (r && r.message && r.message.ok) {
					frappe.show_alert({
						message: r.message.message || __("Connection OK"),
						indicator: "green",
					});
				}
			} finally {
				frappe.dom.unfreeze();
			}
		});
	},

	provider(frm) {
		load_provider_models(frm);
	},
});

function load_provider_models(frm) {
	const field = frm.fields_dict.model_id;
	// Suggestions are hints, never a restriction — allow any typed model_id.
	field.df.ignore_validation = true;
	if (!frm.doc.provider) {
		field.set_data([]);
		return;
	}
	frappe.call({
		method: "flow.flow.doctype.flow_model.flow_model.get_provider_models",
		args: { provider: frm.doc.provider },
		callback: ({ message }) => field.set_data(message || []),
	});
}
