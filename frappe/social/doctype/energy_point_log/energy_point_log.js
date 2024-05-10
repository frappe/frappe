// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Energy Point Log", {
	refresh: function (frm) {
		frm.events.make_reference_name_link(frm);
		if (frm.doc.reverted) {
			frm.set_intro(__("This document has been reverted"));
		} else if (frm.doc.type === "Auto" && frappe.user_roles.includes("System Manager")) {
			frm.add_custom_button(__("Revert"), () => frm.events.show_revert_dialog(frm));
		}
	},
	show_revert_dialog(frm) {
		const revert_dialog = new frappe.ui.Dialog({
			title: __("Revert"),
			fields: [
				{
					fieldname: "reason",
					fieldtype: "Small Text",
					label: __("Reason"),
					reqd: 1,
				},
			],
			primary_action: (values) => {
				return frm
					.call("revert", {
						reason: values.reason,
					})
					.then((res) => {
						let revert_log = res.message;
						revert_dialog.hide();
						revert_dialog.clear();
						frappe.model.docinfo[frm.doc.reference_doctype][
							frm.doc.reference_name
						].energy_point_logs.unshift(revert_log);
						frm.refresh();
					});
			},
			primary_action_label: __("Submit"),
		});
		revert_dialog.show();
	},
	make_reference_name_link(frm) {
		let dt = frm.doc.reference_doctype;
		let dn = frm.doc.reference_name;
		frm.fields_dict.reference_name.$input_wrapper
			.find(".control-value")
			.wrapInner(`<a href='/app/${frappe.router.slug(dt)}/${dn}'></a>`);
	},
});
