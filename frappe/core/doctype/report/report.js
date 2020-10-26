frappe.ui.form.on('Report', {
	refresh: function(frm) {
		if (frm.doc.is_standard === "Yes" && !frappe.boot.developer_mode) {
			// make the document read-only
			frm.set_read_only();
		}

		let doc = frm.doc;
		frm.add_custom_button(__("Show Report"), function() {
			switch(doc.report_type) {
				case "Report Builder":
					frappe.set_route('List', doc.ref_doctype, 'Report', doc.name);
					break;
				case "Query Report":
					frappe.set_route("query-report", doc.name);
					break;
				case "Script Report":
					frappe.set_route("query-report", doc.name);
					break;
				case "Custom Report":
					frappe.set_route("query-report", doc.name);
					break;
			}
		}, "fa fa-table");

		if (doc.is_standard === "Yes") {
			frm.add_custom_button(doc.disabled ? __("Enable Report") : __("Disable Report"), function() {
				frm.call('toggle_disable', {
					disable: doc.disabled ? 0 : 1
				}).then(() => {
					frm.reload_doc();
				});
			}, doc.disabled ? "fa fa-check" : "fa fa-off");
		}

		frm.events.report_type(frm);
	},

	ref_doctype: function(frm) {
		if(frm.doc.ref_doctype) {
			frm.trigger("set_doctype_roles");
		}
	},

	report_type: function(frm) {
		frm.set_intro("");
		switch(frm.doc.report_type) {
			case "Report Builder":
				frm.set_intro(__("Report Builder reports are managed directly by the report builder. Nothing to do."));
				break;
			case "Query Report":
				frm.set_intro(__("Write a SELECT query. Note result is not paged (all data is sent in one go).")
					+ __("To format columns, give column labels in the query.") + "<br>"
					+ __("[Label]:[Field Type]/[Options]:[Width]") + "<br><br>"
					+ __("Example:") + "<br>"
					+ "Employee:Link/Employee:200" + "<br>"
					+ "Rate:Currency:120" + "<br>")
				break;
			case "Script Report":
				frm.set_intro(__("Write a Python file in the same folder where this is saved and return column and result."));
				break;
		}
	},

	set_doctype_roles: function(frm) {
		return frm.call('set_doctype_roles').then(() => {
			frm.refresh_field('roles');
		});
	}
})
