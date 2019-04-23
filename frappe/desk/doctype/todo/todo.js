// bind events

frappe.ui.form.on("ToDo", {
	onload: function (frm) {
		frm.set_query("reference_type", function (txt) {
			return {
				"filters": {
					"issingle": 0,
				}
			};
		});
	},

	validate: function (frm) {
		if (frm.doc.is_repeating && frm.doc.__islocal) {
			frm.trigger("new_auto_repeat_prompt");
		}
	},

	refresh: function (frm) {
		if (frm.doc.reference_type && frm.doc.reference_name) {
			frm.add_custom_button(__(frm.doc.reference_name), function () {
				frappe.set_route("Form", frm.doc.reference_type, frm.doc.reference_name);
			});
		}

		if (!frm.doc.__islocal) {
			if (frm.doc.status !== "Closed") {
				frm.add_custom_button(__("Close"), function () {
					frm.set_value("status", "Closed");
					frm.save(null, function () {
						// back to list
						frappe.set_route("List", "ToDo");
					});
				}, "fa fa-check", "btn-success");
			} else {
				frm.add_custom_button(__("Reopen"), function () {
					frm.set_value("status", "Open");
					frm.save();
				}, null, "btn-default");
			}
			frm.add_custom_button(__("New"), function () {
				frappe.new_doc("ToDo")
			}, null, "btn-default");
		}
	},

	new_auto_repeat_prompt: function (frm) {
		const fields = [
			{
				'fieldname': 'start_date',
				'fieldtype': 'Date',
				'label': __('Start Date'),
				'default': frappe.datetime.nowdate()
			},
			{
				'fieldname': 'end_date',
				'fieldtype': 'Date',
				'label': __('End Date')
			},
			{
				'fieldname': 'frequency',
				'fieldtype': 'Select',
				'label': __('Frequency'),
				'reqd': 1,
				'options': [
					{'label': __('Daily'), 'value': 'Daily'},
					{'label': __('Weekly'), 'value': 'Weekly'},
					{'label': __('Monthly'), 'value': 'Monthly'},
					{'label': __('Quarterly'), 'value': 'Quarterly'},
					{'label': __('Half-yearly'), 'value': 'Half-yearly'},
					{'label': __('Yearly'), 'value': 'Yearly'}
				]
			}
		];

		frappe.prompt(fields, function (values) {
			frappe.call({
				method: "frappe.desk.doctype.auto_repeat.auto_repeat.make_auto_repeat",
				args: {
					'doctype': frm.doc.doctype,
					'docname': frm.doc.name,
					'submit': true,
					'opts': {
						'start_date': values['start_date'],
						'end_date': values['end_date'],
						'frequency': values['frequency']
					}
				},
				callback: function (r) {
					if (r.message) {
						frappe.show_alert({
							'message': __("Successfully created repeating task"),
							'indicator': 'green'
						});
					}
				}
			});
		},
		__('Auto Repeat'),
		__('Submit')
		);
	}
});
