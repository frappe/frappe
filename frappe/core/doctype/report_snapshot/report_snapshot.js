// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Report Snapshot', {
	refresh: function(frm) {
		if (!frm.doc.disabled) {
			frm.add_custom_button('Sync', () => {
				frappe.call({
					method: 'frappe.core.doctype.report_snapshot.report_snapshot.take_snapshot',
					args: {
						docname: frm.doc.name
					}
				})
			})
			if (frm && frm.doc && frm.doc.report && !frm.doc.filters) {
				render_report_filters(frm)
			}
		}
	},
	report: render_report_filters
});

function render_report_filters(frm) {

	frappe.call({
		method: "frappe.desk.query_report.get_script",
		args: {
			report_name: frm.doc.report
		},
		callback: function (r) {
			frm.doc.filters = []
			frappe.dom.eval(r.message.script || "");
			frm.script_setup_for = frm.doc.report;
			frappe.query_reports[frm.doc.report].filters.forEach(filter => {
				var _filter = {
					'label': filter.label,
					'field_name': filter.fieldname
				}
				frm.add_child('filters', _filter)
			});
			frm.refresh_field('filters')
		}
	});
}