/**
 * frappe.views.ReportView
 */
frappe.provide('frappe.views');

frappe.views.ReportView = frappe.views.ListRenderer.extend({
	name: 'Report',

	render_view(values) {

		if (this.datatable && this.wrapper.find('.data-table').length) {
			const rows = this.build_rows(values);
			this.datatable.appendRows(rows);
			return;
		}

		this.datatable = new DataTable(this.wrapper[0], {
			data: this.get_data(values),
			enableClusterize: true,
			addCheckbox: this.can_delete(),
			takeAvailableSpace: true,
			editing: this.get_editing_object.bind(this)
		});
	},

	get_editing_object(colIndex, rowIndex, value, parent) {
		const control = this.render_editing_input(colIndex, value, parent);
		if (!control) return false;

		return {
			initValue: (value) => {
				control.set_focus();
				return control.set_value(value);
			},
			setValue: (value) => {
				const cell = this.datatable.getCell(colIndex, rowIndex);
				let fieldname = this.datatable.getColumn(colIndex).docfield.fieldname;
				let docname = cell.name;

				control.set_value(value);
				return this.set_control_value(docname, fieldname, value);
			},
			getValue: () => {
				return control.get_value();
			}
		}
	},

	set_control_value(docname, fieldname, value) {
		this.last_updated_doc = docname;
		return new Promise((resolve, reject) => {
			frappe.db.set_value(this.doctype, docname, fieldname, value)
				.then(r => {
					if (r.message) {
						resolve();
					} else {
						reject();
					}
				})
				.fail(reject);
		})
	},

	render_editing_input(colIndex, value, parent) {
		const col = this.datatable.getColumn(colIndex);

		if (!this.validate_cell_editing(col.docfield)) {
			return false;
		}

		// make control
		const control = frappe.ui.form.make_control({
			df: col.docfield,
			parent: parent,
			render_input: true
		});
		control.set_value(value);
		control.toggle_label(false);
		control.toggle_description(false);

		return control;
	},

	validate_cell_editing(docfield) {
		if (!docfield) return false;

		const is_standard_field = frappe.model.std_fields_list.includes(docfield.fieldname);
		const is_read_only = docfield.read_only;
		if(docfield.fieldname !== "idx" && is_standard_field || is_read_only) {
			return false;
		} else if(!frappe.boot.user.can_write.includes(this.doctype)) {
			frappe.throw({
				title:__('Not Permitted'),
				message:__("No permission to edit")
			});
			return false;
		}
		return true;
	},

	refresh_on_dirty(docname, user) {
		return this.last_updated_doc !== docname && user !== frappe.session.user;
	},

	get_data(values) {
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
			let [fieldname, doctype] = c;
			let docfield = frappe.meta.docfield_map[doctype || this.doctype][fieldname];

			if(!docfield) {
				docfield = frappe.model.get_std_field(fieldname);

				if(docfield) {
					docfield.parent = this.doctype;
					if(fieldname == "name") {
						docfield.options = this.doctype;
					}
				}
			}
			if(!docfield) return;

			const title = __(docfield ? docfield.label : toTitle(fieldname));
			const editable = fieldname !== 'name' && !docfield.read_only;

			return {
				id: fieldname,
				field: fieldname,
				docfield: docfield,
				name: title,
				content: title, // required by datatable
				width: (docfield ? cint(docfield.width) : 120) || 120,
				editable: editable
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
						name: d.name,
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