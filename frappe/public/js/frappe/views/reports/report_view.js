/**
 * frappe.views.ReportView
 */
frappe.provide('frappe.views');

frappe.views.ReportView = frappe.views.ListRenderer.extend({
	name: 'Report',

	render_view(values) {
		this.datatable = new DataTable(this.wrapper, {
			data: this.get_data(values),
			enableLogs: false,
			enableClusterize: true,
			addCheckbox: this.can_delete(),
			// editing: (colIndex, rowIndex, value, parent) => {
			// 	const control = me.render_editing_input(colIndex, value, parent);
			// 	if (!control) return false;

			// 	return {
			// 		initValue: (value) => {
			// 			return control.set_value(value);
			// 		},
			// 		setValue: (value) => {
			// 			return me.update_value_on_server(
			// 				this.doctype,
			// 				get_docname(rowIndex),
			// 				get_fieldname(colIndex),
			// 				value
			// 			).then(r => {
			// 				if(r.message) {
			// 					const updated_value = r.message[get_fieldname(colIndex)];
			// 					return control.set_value(value);
			// 				}
			// 			});
			// 		},
			// 		getValue: () => {
			// 			return control.get_value();
			// 		}
			// 	}
			// }
		});
	},

	get_data(values) {
		// this.make_columns();
		return {
			columns: this.columns,
			rows: this.build_rows(values)
		}
	},

	set_columns() {
		var columns = [];

		const invalid_columns = [
			'_seen', '_comments', '_user_tags', '_assign', '_liked_by', 'docstatus'
		];

		// load from user settings
		if(this.user_settings.fields) {
			this.user_settings.fields.map(field => {
				var coldef = this.get_column_info_from_field(field);
				if(!invalid_columns.includes(coldef[0])) {
					columns.push(coldef);
				}
			});
		}

		if(columns.length === 0) {
			// build default columns
			var columns = [['name', this.doctype]];

			const default_fields = frappe.meta.docfield_list[this.doctype];

			default_fields.filter(df => {
				return (df.in_standard_filter || df.in_list_view) && df.fieldname!='naming_series'
				&& !in_list(frappe.model.no_value_type, df.fieldtype)
				&& !df.report_hide
			}).map(df => {
				columns.push([df.fieldname, df.parent]);
			});
		}

		this.columns = this.build_columns(columns);

		// this.page.footer.on('click', '.show-all-data', function() {
		// 	me.show_all_data = $(this).prop('checked');
		// 	me.run();
		// })
	},

	build_columns(columns) {
		return columns.map(c => {

			var docfield = frappe.meta.docfield_map[c[1] || this.doctype][c[0]];
			if(!docfield) {
				var docfield = frappe.model.get_std_field(c[0]);

				if(docfield) {
					docfield.parent = this.doctype;
					if(c[0]=="name") {
						docfield.options = this.doctype;
					}
				}
			}
			if(!docfield) return;

			const title = __(docfield ? docfield.label : toTitle(c[0]));

			return {
				id: c[0],
				field: c[0],
				docfield: docfield,
				name: title,
				content: title, // required by datatable
				width: (docfield ? cint(docfield.width) : 120) || 120
			}
		});
	},

	build_rows(data) {
		return data.map(d => {
			return this.columns.map(col => {
				if (col.name === 'Sr.') {
					return { content: i };
				}
				if (col.field in d) {
					const value = d[col.field];
					return {
						content: value,
						format: function(value) {
							return frappe.format(value, col.docfield, {always_show_decimals: true});
						}
					}
				}
				return {
					content: ''
				};
			});
		});
	},

	get_column_info_from_field(t) {
		if(t.indexOf('.')===-1) {
			return [strip(t, '`'), this.doctype];
		} else {
			var parts = t.split('.');
			return [strip(parts[1], '`'), strip(parts[0], '`').substr(3)];
		}
	},

	set_defaults() {
		this._super();
		this.page_title = __('Report:') + ' ' +  this.page_title;
	},
	get_header_html() {
		return '';
	}
});