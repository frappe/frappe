function open_web_template_values_editor(template, current_values = {}) {
	return new Promise(resolve => {
		frappe.model.with_doc("Web Template", template).then((doc) => {
			let d = new frappe.ui.Dialog({
				title: __("Edit Values"),
				fields: get_fields(doc),
				primary_action(values) {
					d.hide();
					resolve(values);
				},
			});
			d.set_values(current_values);
			d.show();

			d.sections.forEach((sect) => {
				let fields_with_value = sect.fields_list.filter(
					(field) => current_values[field.df.fieldname]
				);

				if (fields_with_value.length) {
					sect.collapse(false);
				}
			});
		});
	});

	function get_fields(doc) {
		let normal_fields = [];
		let table_fields = [];

		let current_table = null;
		for (let df of doc.fields) {
			if (current_table) {
				current_table.fields = current_table.fields || [];

				if (df.fieldtype != 'Table Break') {
					current_table.fields.push(df);
				} else {
					table_fields.push(df);
					current_table = df;
				}
			} else if (df.fieldtype != 'Table Break') {
				normal_fields.push(df);
			} else {
				table_fields.push(df);
				current_table = df;
			}
		}

		let fields = [
			...normal_fields,
			...table_fields.map(tf => {
				let data = current_values[tf.fieldname] || [];
				return {
					label: tf.label,
					fieldname: tf.fieldname,
					fieldtype: 'Table',
					fields: tf.fields.map((df, i) => ({
						...df,
						in_list_view: i <= 1,
						columns: tf.fields.length == 1 ? 10 : 5
					})),
					data,
					get_data: () => data
				};
			})
		];

		return fields;
	}
}
