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

		this.setup_datatable(values);
		this.setup_column_picker();
	},

	setup_datatable(values) {
		this.datatable = new DataTable(this.wrapper[0], {
			data: this.get_data(values),
			enableClusterize: true,
			addCheckbox: this.can_delete(),
			takeAvailableSpace: true,
			editing: this.get_editing_object.bind(this)
		});

		this.list_view.wrapper.one('render-complete', () => {
			if (this.last_action === 'add_column') {
				// if new column was added, scroll to it
				this.datatable.scrollToLastColumn();
			}
			this.last_action = 'refresh';
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

	set_fields() {
		this.stats = ['_user_tags'];

		if (this.user_settings.fields) {
			this._fields = this.user_settings.fields;
			this.build_fields();
			return;
		}

		this._fields = [];

		const add_field = fieldname => {
			if (!fieldname) return;
			let doctype = this.doctype;
			if (typeof fieldname === 'object') {
				// df is passed
				const df = fieldname;
				fieldname = df.fieldname;
				doctype = df.parent;
			}

			this._fields.push([fieldname, doctype]);
		}

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
				&& !frappe.model.no_value_type.includes(df.fieldtype)
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
		this.settings.add_fields.map(add_field);

		this.build_fields();
	},

	build_fields() {
		//de-dup
		this._fields = this._fields.uniqBy(f => f[0] + f[1]);
		// build this.fields
		this.fields = this._fields.map(f => frappe.model.get_full_column_name(f[0], f[1]));
		// save in user_settings
		frappe.model.user_settings.save(this.doctype, 'Report', {
			fields: this._fields
		});
	},

	set_columns() {
		this.columns = this._fields.map(this.build_column);
		this.add_add_column();
	},

	add_add_column() {
		const dropdown_html =`<div class="btn-group btn-add-column">
				<span class="octicon octicon-plus dropdown-toggle" data-toggle="dropdown"></span>
				<ul class="dropdown-menu"></ul>
			</div>
		`;
		const extra_column = {
			content: dropdown_html,
			editable: false,
			sortable: false,
			resizable: false,
			focusable: false
		}
		this.columns.push(extra_column);
	},

	setup_column_picker() {
		const $header = $(this.datatable.header);
		const $btn_add_column = $header
			.find('.data-table-col .btn-add-column')
		const $content = $btn_add_column.closest('.content');
		$content.css('overflow', 'visible');
		$content.find('ul').css({
			right: 0,
			left: 'auto'
		});

		this.update_column_picker_dropdown();

		// friendly click
		$btn_add_column
			.closest('.data-table-col')
			.on('click', '.content, li', (e) => {
				const $target = $(e.currentTarget);
				if ($target.is('.content')) {
					$btn_add_column.toggleClass('open');
					e.stopPropagation();
				}
				if ($target.is('li')) {
					const { fieldname } = $target.data();
					this.add_column_to_datatable(fieldname);
				}
			});
	},

	add_column_to_datatable(fieldname) {
		const field = [fieldname, this.doctype];
		this._fields.push(field);

		this.build_fields();
		this.set_columns();

		this.datatable.destroy();
		this.last_action = 'add_column';

		this.list_view.refresh(true);
	},

	update_column_picker_dropdown() {
		if (!this.datatable) return;
		const $header = $(this.datatable.header);
		const remaining_columns = this.get_remaining_columns();
		const html = remaining_columns.map(df => `<li data-fieldname="${df.fieldname}"><a>${df.label}</a></li>`);
		$header.find('ul').html(html);
	},

	get_remaining_columns() {
		const valid_fields = frappe.meta.docfield_list[this.doctype].filter(df =>
			!in_list(frappe.model.no_value_type, df.fieldtype) &&
			!df.report_hide && df.fieldname !== 'naming_series' &&
			!df.hidden
		);
		const shown_fields = this.columns.map(c => c.docfield && c.docfield.fieldname);
		return valid_fields.filter(df => !shown_fields.includes(df.fieldname));
	},

	build_column(c) {
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