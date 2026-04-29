// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Global Search Settings", {
	refresh: function (frm) {
		frappe.realtime.on("global_search_settings", (data) => {
			if (data.progress) {
				frm.dashboard.show_progress(
					"Setting up Global Search",
					(data.progress / data.total) * 100,
					data.msg
				);
				if (data.progress === data.total) {
					frm.dashboard.hide_progress("Setting up Global Search");
				}
			}
		});

		frm.add_custom_button(__("Reset"), function () {
			frappe.call({
				method: "frappe.desk.doctype.global_search_settings.global_search_settings.reset_global_search_settings_doctypes",
				callback: function () {
					frappe.show_alert({
						message: __("Global Search Document Types Reset."),
						indicator: "green",
					});
					frm.refresh();
				},
			});
		});
	},
});

frappe.ui.form.on("Global Search DocType", {
	configure: function (frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (!row.document_type) {
			frappe.msgprint(__("Please select Document Type first."));
			return;
		}
		frappe.model.with_doctype(row.document_type, () => {
			frappe.global_search_settings.show_configure_search_fields_dialog(
				row.document_type,
				frm
			);
		});
	},
});

frappe.provide("frappe.global_search_settings");

frappe.global_search_settings.show_configure_search_fields_dialog = function (doctype, frm) {
	frappe.call({
		method: "frappe.desk.doctype.global_search_settings.global_search_settings.get_global_search_field_options",
		args: { doctype },
		callback(r) {
			const options = r.message?.options || [];
			const default_global_search_fields = r.message?.default_global_search_fields || [];

			const dialog = new frappe.ui.Dialog({
				title: __("Configure search fields of {0}", [__(doctype)]),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "search_bar",
					},
					{
						label: __(doctype),
						fieldname: "search_fields",
						fieldtype: "MultiCheck",
						columns: 2,
						sort_options: false,
						options,
					},
				],

				primary_action_label: __("Save"),
				primary_action() {
					const checked = dialog.get_field("search_fields").get_checked_options();
					frappe.call({
						method: "frappe.desk.doctype.global_search_settings.global_search_settings.update_global_search_fields",
						args: { doctype, fields: checked },
						freeze: true,
						freeze_message: __("Updating search index"),
						callback: function (r) {
							if (r.exc) {
								frappe.msgprint(r.exc);
							} else {
								dialog.hide();
								frappe.show_alert({
									message: __("Global Search Fields Updated."),
									indicator: "green",
								});
								if (frm) {
									frm.refresh();
								}
							}
						},
					});
				},

				secondary_action_label: __("Reset"),
				secondary_action() {
					const field = dialog.get_field("search_fields");
					const defaults = new Set(default_global_search_fields);
					field.selected_options = field.options
						.filter((o) => defaults.has(o.value))
						.map((o) => o.value);
					field.select_options(field.selected_options);
				},
			});

			dialog.get_field("search_bar").$wrapper.html(`
				<div class="filters-search mb-3">
					<input
						type="text"
						placeholder="${__("Search")}"
						data-element="search"
						class="form-control input-xs"
					>
				</div>
			`);

			dialog.show();

			frappe.utils.setup_search(dialog.$body, ".unit-checkbox", ".label-area");
		},
	});
};
