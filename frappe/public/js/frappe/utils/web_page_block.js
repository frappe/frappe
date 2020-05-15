frappe.ui.form.on('Web Page Block', {
	edit_values(frm, cdt, cdn) {
		let row = frm.selected_doc;
		frappe.model.with_doc('Web Template', row.web_template).then(doc => {
			let d = new frappe.ui.Dialog({
				title: __('Edit Values'),
				fields: doc.fields.map(df => {
					if (df.fieldtype == "Section Break") {
						df.collapsible = 1;
					}
					return df
				}),
				primary_action(values) {
					frappe.model.set_value(
						cdt,
						cdn,
						'web_template_values',
						JSON.stringify(values)
					);
					d.hide();
				}
			});
			let values = JSON.parse(row.web_template_values || '{}');
			d.set_values(values);
			d.show();
		});
	}
});
