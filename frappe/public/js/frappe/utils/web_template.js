function open_web_template_values_editor(template, current_values = {}) {
	return new Promise((resolve) => {
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
		let fields_to_return = [];  // Used to maintain the order of fields
		let current_table = null;
	
		for (let df of doc.fields) {
			// When encountering a Table Break field
			if (df.fieldtype === "Table Break") {
				// Check if a table with the same label is already being processed
				if (current_table && current_table.label === df.label) {
					// If it's the same table, consider the table's range as ended
					fields_to_return.push({
						label: current_table.label,
						fieldname: current_table.fieldname,
						fieldtype: "Table",
						fields: current_table.fields.map((df, i) => ({
							...df,
							in_list_view: i <= 1,
							columns: current_table.fields.length === 1 ? 10 : 5,
						})),
						data: current_values[current_table.fieldname] || [],
						get_data: () => current_table && current_table.fieldname ? current_values[current_table.fieldname] || [] : [],
					});
					current_table = null;
				} else {
					// If it's a new table, start a new table
					current_table = {
						label: df.label,
						fieldname: df.fieldname,
						fields: [],
					};
				}
			} else if (current_table) {
				// If currently processing a table, add the field to the table's fields
				current_table.fields.push(df);
			} else {
				// If not in a table range, add the field directly to fields_to_return
				fields_to_return.push(df);
			}
		}
	
		// Handle the last unfinished table
		if (current_table) {
			fields_to_return.push({
				label: current_table.label,
				fieldname: current_table.fieldname,
				fieldtype: "Table",
				fields: current_table.fields.map((df, i) => ({
					...df,
					in_list_view: i <= 1,
					columns: current_table.fields.length === 1 ? 10 : 5,
				})),
				data: current_values[current_table.fieldname] || [],
				get_data: () => current_values[current_table.fieldname] || [],
			});
		}
	
		return fields_to_return;
	}
}
