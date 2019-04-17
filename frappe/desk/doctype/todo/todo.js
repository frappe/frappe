// bind events

frappe.ui.form.on("ToDo", {
	onload: function(frm) {
		frm.set_query("reference_type", function(txt) {
			return {
				"filters": {
					"issingle": 0,
				}
			};
		});
	},

	validate: function(frm)
	{
		frm.trigger("Save");
	},

	refresh: function(frm) {
		if(frm.doc.reference_type && frm.doc.reference_name) {
			frm.add_custom_button(__(frm.doc.reference_name), function() {
				frappe.set_route("Form", frm.doc.reference_type, frm.doc.reference_name);
			});
		}

		if (!frm.doc.__islocal) {
			if(frm.doc.status!=="Closed") {
				frm.add_custom_button(__("Close"), function() {
					frm.set_value("status", "Closed");
					frm.save(null, function() {
						// back to list
						frappe.set_route("List", "ToDo");
					});
				}, "fa fa-check", "btn-success");
			} else {
				frm.add_custom_button(__("Reopen"), function() {
					frm.set_value("status", "Open");
					frm.save();
				}, null, "btn-default");
			}
			frm.add_custom_button(__("New"), function() {
				frappe.new_doc("ToDo")
			}, null, "btn-default");
		}
	},

	Save: function(frm)
	{
			frappe.prompt([
				{	'fieldname': 'start_date',
					'fieldtype': 'Date',
					'label': 'Start Date',
					'default': frappe.datetime.nowdate()
				},
				{	'fieldname': 'end_date',
					'fieldtype': 'Date',
					'label': 'End Date',
				},
				{	'fieldname': 'frequency',
					'fieldtype': 'Select',
					'options': [
						'Daily',
						'Weekly',
						'Monthly',
						'Quarterly',
						'Half-yearly',
						'Yearly'
					],
					'label': 'Frequency',
					'reqd': 1
				},
			],
			function(values){
				frappe.call({
					method: "frappe.desk.doctype.todo.todo.recurring",
					args: {
						todo: frm.doc.name,
						start_date: values["start_date"],
						end_date: values["end_date"],
						frequency: values["frequency"]
					},
					callback: function(r) {
						frappe.confirm(
							'ToDo Recurring Successful',
							function(){
								window.close();
							},
							function(){
								show_alert('Recurring Created')
							}
						)
					}
				});
			},
			'Auto Repeat',
			'Submit'
			)
	}
});
