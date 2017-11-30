/**
 * frappe.views.ReportView
 */
frappe.provide('frappe.views');

frappe.views.ReportView = class ReportView extends frappe.views.ListView {
	setup_defaults() {
		super.setup_defaults();
		this.page_title = __('Report:') + ' ' + this.page_title;
	}

	setup_view() {
		this.setup_columns();
	}

	render() {
		this.setup_datatable(this.data);
	}

	setup_datatable(values) {
		this.datatable = new DataTable(this.$result[0], {
			data: this.get_data(values),
			enableClusterize: true,
			addCheckbox: this.can_delete,
			takeAvailableSpace: true,
			editing: this.get_editing_object.bind(this),
			events: {
				onRemoveColumn: (column) => {
					this.remove_column_from_datatable(column);
				},
				onSwitchColumn: (column1, column2) => {
					this.switch_column(column1, column2);
				}
			},
			headerDropdown: [{
				label: 'Add column',
				action: (column) => {
					const options = this.get_remaining_columns()
						.map(d => ({label:d.label, value: d.fieldname}));

					const d = new frappe.ui.Dialog({
						title: __('Add column'),
						fields: [
							{ label: __('Column Name'), fieldtype: 'Select', options: options }
						],
						primary_action: (values) => {
							if (!values.column_name) return;
							this.add_column_to_datatable(values.column_name, column.colIndex);
							d.hide();
						}
					});

					d.show();
				}
			}]
		});
	}

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
	}

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
	}

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
	}

	validate_cell_editing(docfield) {
		if (!docfield) return false;
		const is_standard_field = frappe.model.std_fields_list.includes(docfield.fieldname);
		const is_read_only = docfield.read_only;
		if (docfield.fieldname !== "idx" && is_standard_field || is_read_only) {
			return false;
		} else if (!frappe.boot.user.can_write.includes(this.doctype)) {
			frappe.throw({
				title: __('Not Permitted'),
				message: __("No permission to edit")
			});
			return false;
		}
		return true;
	}

	get_data(values) {
		return {
			columns: this.columns,
			rows: this.build_rows(values)
		}
	}

	set_fields() {
		// get from user_settings
		if (this.view_user_settings.fields) {
			this._fields = this.view_user_settings.fields;
			return;
		}

		// get fields from meta
		this._fields = [];
		const add_field = f => this._add_field(f);

		// default fields
		[
			'name',
			this.meta.title_field,
			this.meta.image_field
		].map(add_field);

		// fields in_list_view or in_standard_filter
		const fields = this.meta.fields.filter(df => {
			return (df.in_list_view || df.in_standard_filter)
				&& frappe.perm.has_perm(this.doctype, df.permlevel, 'read')
				&& frappe.model.is_value_type(df.fieldtype)
				&& !df.report_hide
		});

		fields.map(add_field);

		// currency fields
		fields.filter(
			df => df.fieldtype === 'Currency' && df.options
		).map(df => {
			if (df.options.includes(':')) {
				add_field(df.options.split(':')[1]);
			} else {
				add_field(df.options);
			}
		});

		// image fields
		const image_fields = fields.filter(
			df => df.fieldtype === 'Image'
		).map(df => {
			if (df.options) {
				add_field(df.options);
			} else {
				add_field(df.fieldname);
			}
		});

		// fields in listview_settings
		(this.settings.add_fields || []).map(add_field);
	}

	add_column_to_datatable(fieldname, col_index) {
		const field = [fieldname, this.doctype];
		this._fields.splice(col_index - 1, 0, field);

		this.build_fields();
		this.setup_columns();

		this.datatable.destroy();
		this.refresh(true);
	}

	remove_column_from_datatable(column) {
		const index = this._fields.findIndex(f => column.field === f[0]);
		if (index === undefined) return;
		const field = this._fields[index];
		if (field[0] === 'name') {
			this.refresh(true);
			frappe.throw(__('Cannot remove name field'));
		}
		this._fields.splice(index, 1);
		this.build_fields();
	}

	switch_column(col1, col2) {
		const index1 = this._fields.findIndex(f => col1.field === f[0]);
		const index2 = this._fields.findIndex(f => col2.field === f[0]);
		const _fields = this._fields.slice();

		let temp = _fields[index1];
		_fields[index1] = _fields[index2];
		_fields[index2] = temp;

		this._fields = _fields;
		this.build_fields();
	}

	get_remaining_columns() {
		const valid_fields = frappe.meta.docfield_list[this.doctype].filter(df =>
			!in_list(frappe.model.no_value_type, df.fieldtype) &&
			!df.report_hide && df.fieldname !== 'naming_series' &&
			!df.hidden
		);
		const shown_fields = this.columns.map(c => c.docfield && c.docfield.fieldname);
		return valid_fields.filter(df => !shown_fields.includes(df.fieldname));
	}

	setup_columns() {
		this.columns = this._fields.map(this.build_column);
	}

	build_column(c) {
		let [fieldname, doctype] = c;
		let docfield = frappe.meta.docfield_map[doctype || this.doctype][fieldname];

		if (!docfield) {
			docfield = frappe.model.get_std_field(fieldname);

			if (docfield) {
				docfield.parent = this.doctype;
				if (fieldname == "name") {
					docfield.options = this.doctype;
				}
			}
		}
		if (!docfield) return;

		const title = __(docfield ? docfield.label : toTitle(fieldname));
		const editable = frappe.model.is_non_std_field(fieldname) && !docfield.read_only;

		return {
			id: fieldname,
			field: fieldname,
			docfield: docfield,
			name: title,
			content: title, // required by datatable
			width: (docfield ? cint(docfield.width) : 120) || 120,
			editable: editable
		}
	}

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
						format: function (value) {
							return frappe.format(value, col.docfield, { always_show_decimals: true });
						}
					}
				}
				return {
					content: ''
				};
			});
		});
	}
}
