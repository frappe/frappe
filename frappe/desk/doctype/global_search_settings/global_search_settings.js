// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

function show_configure_search_fields_dialog(doctype, frm) {
	frappe.call({
		method: "frappe.desk.doctype.global_search_settings.global_search_settings.get_global_search_field_options",
		args: { doctype },
		callback(r) {
			const options = r.message || [];

			const dialog = new frappe.ui.Dialog({
				title: __("Configure search fields"),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "doctype_heading",
					},
					{
						fieldtype: "HTML",
						fieldname: "search_bar",
					},
					{
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
									message: __("Search fields updated."),
									indicator: "green",
								});
								if (frm) {
									frm.refresh();
								}
							}
						},
					});
				},
			});

			dialog.get_field("doctype_heading").$wrapper.html(`
				<div class="mb-3 font-weight-bold">${frappe.utils.escape_html(__(doctype))}</div>
			`);

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
}

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
			show_configure_search_fields_dialog(row.document_type, frm);
		});
	},
});
