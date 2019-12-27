export default class ColumnPickerFields extends frappe.views.ReportView {
	show() {}

	get_fields_as_options() {
		let column_map = this.get_columns_for_picker();
		let doctypes = [this.doctype].concat(
			...frappe.meta.get_table_fields(this.doctype).map(df => df.options)
		);
		// flatten array
		return [].concat(
			...doctypes.map(doctype => {
				return column_map[doctype].map(df => {
					let label = df.label;
					let value = df.fieldname;
					if (this.doctype !== doctype) {
						label = `${df.label} (${doctype})`;
						value = `${doctype}:${df.fieldname}`;
					}
					return {
						label,
						value,
						description: value
					};
				});
			})
		);
	}
}
