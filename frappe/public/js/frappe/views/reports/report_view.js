/**
 * frappe.views.ReportView
 */
import DataTable from 'frappe-datatable';

frappe.provide('frappe.views');

frappe.views.ReportView = class ReportView extends frappe.views.ListView {
	get view_name() {
		return 'Report';
	}

	setup_defaults() {
		super.setup_defaults();
		this.page_title = __('Report:') + ' ' + this.page_title;
		this.menu_items = this.report_menu_items();

		const route = frappe.get_route();
		if (route.length === 4) {
			this.report_name = route[3];
		}

		this.add_totals_row = this.view_user_settings.add_totals_row || 0;

		if (this.report_name) {
			return this.get_report_doc()
				.then(doc => {
					this.report_doc = doc;
					this.report_doc.json = JSON.parse(this.report_doc.json);

					this.filters = this.report_doc.json.filters;
					this.order_by = this.report_doc.json.order_by;
					this.add_totals_row = this.report_doc.json.add_totals_row;
					this.page_title = this.report_name;
					this.page_length = this.report_doc.json.page_length || 20;
					this.order_by = this.report_doc.json.order_by || 'modified desc';
				});
		}
	}

	setup_view() {
		this.setup_columns();
		this.bind_charts_button();
	}

	setup_result_area() {
		super.setup_result_area();
		this.$datatable_wrapper = $('<div class="datatable-wrapper">');
		this.$charts_wrapper = $('<div class="charts-wrapper">');
		this.$result.append(this.$charts_wrapper);
		this.$result.append(this.$datatable_wrapper);
	}

	setup_paging_area() {
		super.setup_paging_area();
		const message = __('For comparison, use >5, <10 or =324. For ranges, use 5:10 (for values between 5 & 10).');
		this.$paging_area.find('.level-left').append(
			`<p class="text-muted text-medium margin-left">${message}</p>`
		)
	}

	setup_sort_selector() {
		this.sort_selector = new frappe.ui.SortSelector({
			parent: this.filter_area.$filter_list_wrapper,
			doctype: this.doctype,
			args: this.order_by,
			onchange: this.on_sort_change.bind(this)
		});
	}

	before_render() {
		if (this.report_doc) {
			this.set_dirty_state_for_custom_report();
		} else {
			this.save_report_settings();
		}
	}

	set_dirty_state_for_custom_report() {
		const json = JSON.stringify({
			filters: this.filter_area.get(),
			fields: this.fields,
			order_by: this.sort_selector.get_sql_string(),
			add_totals_row: this.add_totals_row,
			page_length: this.page_length
		});

		const report_json = JSON.stringify({
			filters: this.report_doc.json.filters,
			fields: this.report_doc.json.fields,
			order_by: this.report_doc.json.order_by,
			add_totals_row: this.report_doc.json.add_totals_row,
			page_length: this.report_doc.json.page_length
		});

		if (json != report_json) {
			this.page.set_indicator(__('Not Saved'), 'orange');
		} else {
			this.page.clear_indicator();
		}
	}

	save_report_settings() {
		frappe.model.user_settings.save(this.doctype, 'last_view', this.view_name);

		if (!this.report_name) {
			this.save_view_user_settings({
				fields: this.fields,
				filters: this.filter_area.get(),
				order_by: this.sort_selector.get_sql_string(),
				add_totals_row: this.add_totals_row
			});
		}
	}

	prepare_data(r) {
		let data = r.message || {};
		data = frappe.utils.dict(data.keys, data.values);

		if (this.start === 0) {
			this.data = data;
		} else {
			this.data = this.data.concat(data);
		}
	}

	render(force) {
		if (this.data.length === 0) return;
		this.render_count();

		if (this.chart) {
			this.refresh_charts();
		}
		if (this.datatable && !force) {
			this.datatable.refresh(this.get_data(this.data), this.columns);
			return;
		}
		this.setup_datatable(this.data);
	}

	render_count() {
		let $list_count = this.$paging_area.find('.list-count');
		if (!$list_count.length) {
			this.$paging_area.find('.btn-more').addClass('margin-left');
			$list_count = $('<span>')
				.addClass('text-muted text-medium list-count')
				.prependTo(this.$paging_area.find('.level-right'));
		}
		this.get_count_str()
			.then(str => {
				$list_count.text(str);
			});
	}

	on_update(data) {
		if (this.doctype === data.doctype && data.name) {
			// flash row when doc is updated by some other user
			const flash_row = data.user !== frappe.session.user;
			if (this.data.find(d => d.name === data.name)) {
				// update existing
				frappe.db.get_doc(data.doctype, data.name)
					.then(doc => this.update_row(doc, flash_row));
			} else {
				// refresh
				this.refresh();
			}
		}
	}

	update_row(doc, flash_row) {
		const to_refresh = [];

		this.data = this.data.map((d, i) => {
			if (d.name === doc.name) {
				for (let fieldname in d) {
					if (fieldname.includes(':')) {
						// child table field
						const [cdt, _field] = fieldname.split(':');
						const cdt_row = Object.keys(doc)
							.filter(key => Array.isArray(doc[key]) && doc[key][0].doctype === cdt)
							.map(key => doc[key])
							.map(a => a[0])
							.filter(cdoc => cdoc.name === d[cdt + ':name'])[0];
						if (cdt_row) {
							d[fieldname] = cdt_row[_field];
						}
					} else {
						d[fieldname] = doc[fieldname];
					}
				}
				to_refresh.push([d, i]);
			}
			return d;
		});

		// indicate row update
		const _flash_row = (rowIndex) => {
			if (!flash_row) return;
			const $row = this.$result.find(`.dt-row[data-row-index="${rowIndex}"]`);
			$row.addClass('row-update');
			setTimeout(() => $row.removeClass('row-update'), 500);
		};

		to_refresh.forEach(([data, rowIndex]) => {
			const new_row = this.build_row(data);
			this.datatable.refreshRow(new_row, rowIndex);
			_flash_row(rowIndex);
		});
	}

	setup_datatable(values) {
		this.$datatable_wrapper.empty();
		this.datatable = new DataTable(this.$datatable_wrapper[0], {
			columns: this.columns,
			data: this.get_data(values),
			getEditor: this.get_editing_object.bind(this),
			checkboxColumn: true,
			inlineFilters: true,
			cellHeight: 37,
			events: {
				onRemoveColumn: (column) => {
					this.remove_column_from_datatable(column);
				},
				onSwitchColumn: (column1, column2) => {
					this.switch_column(column1, column2);
				},
				onCheckRow: () => {
					const checked_items = this.get_checked_items();
					this.toggle_actions_menu_button(checked_items.length > 0);
				}
			},
			hooks: {
				totalAccumulator: frappe.utils.report_total_accumulator
			},
			headerDropdown: [{
				label: __('Add Column'),
				action: (datatabe_col) => {
					let columns_in_picker = [];
					const columns = this.get_columns_for_picker();

					columns_in_picker = columns[this.doctype]
						.filter(df => !this.is_column_added(df))
						.map(df => ({
							label: __(df.label),
							value: df.fieldname
						}));

					delete columns[this.doctype];

					for (let cdt in columns) {
						columns[cdt]
							.filter(df => !this.is_column_added(df))
							.map(df => ({
								label: __(df.label) + ` (${cdt})`,
								value: df.fieldname + ',' + cdt
							}))
							.forEach(df => columns_in_picker.push(df));
					}

					const d = new frappe.ui.Dialog({
						title: __('Add Column'),
						fields: [
							{
								label: __('Select Column'),
								fieldname: 'column',
								fieldtype: 'Autocomplete',
								options: columns_in_picker
							},
							{
								label: __('Insert Column Before {0}', [datatabe_col.docfield.label.bold()]),
								fieldname: 'insert_before',
								fieldtype: 'Check'
							}
						],
						primary_action: ({ column, insert_before }) => {
							if (!columns_in_picker.map(col => col.value).includes(column)) {
								frappe.show_alert(__('Invalid column'));
								d.hide();
								return;
							}

							let doctype = this.doctype;
							if (column.includes(',')) {
								[column, doctype] = column.split(',');
							}


							let index = datatabe_col.colIndex;
							if (insert_before) {
								index = index - 1;
							}

							this.add_column_to_datatable(column, doctype, index);
							d.hide();
						}
					});

					d.show();
				}
			}]
		});
	}

	bind_charts_button() {
		this.list_sidebar.sidebar.find('.charts-menu').removeClass('hide');
		this.list_sidebar.sidebar.on('click', '.toggle-charts', (e) => {
			e.preventDefault();
			this.toggle_charts();
		});
		this.list_sidebar.sidebar.on('click', '.configure-charts', (e) => {
			e.preventDefault();
			this.get_chart_data().then(() => this.refresh_charts());
		});
		this.refresh_charts_sidebar_button();
	}

	refresh_charts_sidebar_button() {
		// show configure charts button if charts is shown
		const $configure_btn = this.list_sidebar.sidebar.find('.configure-charts');
		const charts_visible = this.chart && !this.$charts_wrapper.hasClass('hidden');

		if (charts_visible) {
			$configure_btn.removeClass('hidden');
		} else {
			$configure_btn.addClass('hidden');
		}
	}

	toggle_charts() {
		if (!this.chart) {
			this.setup_charts();
			return;
		}
		this.$charts_wrapper.toggleClass('hidden');

		if (!this.$charts_wrapper.hasClass('hidden')) {
			this.chart.refresh();
		}

		this.refresh_charts_sidebar_button();
	}

	setup_charts() {
		this.get_chart_data()
			.then(args => {
				let data = {
					labels: args.labels,
					datasets: args.datasets
				};

				this.last_chart_type = args.chart_type;

				const get_df = (field) => frappe.meta.get_docfield(this.doctype, field);
				const get_doc = (value, field) => this.data.find(d => d[field] === value);

				this.chart = new Chart(this.$charts_wrapper[0], {
					title: __("{0} Chart", [this.doctype]),
					data: data,
					type: args.chart_type,
					height: 150,
					colors: ['violet', 'light-blue', 'orange', 'red'],

					format_tooltip_x: value => value.doc.name,
					format_tooltip_y:
						value => frappe.format(value, get_df(value.field), { always_show_decimals: true, inline: true }, get_doc(value.doc))
				});

				this.refresh_charts_sidebar_button();
			});
	}

	refresh_charts() {
		if (!this.chart) return;
		const { x_field, y_fields, chart_type } = this.chart_args;
		const args = this.get_chart_args(x_field, y_fields, chart_type);
		this.chart.update_values(args.datasets, args.labels);
		this.chart.refresh();

		if (args.chart_type !== this.last_chart_type) {
			this.chart.get_different_chart(args.chart_type);
		}
	}

	get_chart_data() {
		return new Promise(resolve => {
			const cur_list_fields = this.fields.map(f => f[0]);
			const x_fields = this.meta.fields.filter(df =>
				!df.hidden && cur_list_fields.includes(df.fieldname)
			).map(df => df.fieldname);
			const y_fields = this.meta.fields.filter(df =>
				!df.hidden && frappe.model.is_numeric_field(df)
				&& cur_list_fields.includes(df.fieldname)
			).map(df => df.fieldname);

			const defaults = this.chart_args || {};

			const dialog = new frappe.ui.Dialog({
				title: __('Configure Chart'),
				fields: [
					{
						label: __('X Axis Field'),
						fieldtype: 'Autocomplete',
						fieldname: 'x_axis',
						options: x_fields,
						default: defaults.x_field
					},
					{
						label: __('Y Axis Fields'),
						fieldtype: 'MultiSelect',
						fieldname: 'y_axes',
						options: y_fields,
						description: __('Showing only Numeric fields from Report'),
						default: defaults.y_fields
					},
					{
						label: __('Chart Type'),
						fieldtype: 'Select',
						options: ['Bar', 'Line', 'Pie', 'Percentage'],
						fieldname: 'chart_type',
						default: toTitle(defaults.chart_type || 'Bar')
					}
				],
				primary_action: ({ x_axis, y_axes, chart_type }) => {
					y_axes = y_axes.split(',').map(d => d.trim()).filter(Boolean);

					if (!(
						y_axes.every(d => y_fields.includes(d))
						&& x_fields.includes(x_axis)
					)) return;

					const args = this.get_chart_args(x_axis, y_axes, chart_type);
					this.chart_args = args;
					resolve(args);
					dialog.hide();
				}
			});

			dialog.show();
		});
	}

	get_chart_args(x_axis, y_axes, chart_type) {
		const labels = this.data.map(d => {
			// HACK: labels need strings,
			// so we return objects that
			// look like strings and also
			// monkey patch the doc
			// javascript is awesome

			// O.o

			return {
				doc: d,
				toString() {
					return d[x_axis];
				},
				slice: String.prototype.slice
			};
		});

		return {
			chart_type: chart_type.toLowerCase(),
			x_field: x_axis,
			y_fields: y_axes,
			labels: labels,
			datasets: y_axes.map(y_axis => ({
				name: frappe.meta.get_docfield(this.doctype, y_axis).label,
				values: this.data.map(d => ({
					doc: d,
					field: y_axis,
					toString() {
						return d[y_axis];
					},
					slice: String.prototype.slice
				}))
			}))
		};
	}

	get_editing_object(colIndex, rowIndex, value, parent) {
		const control = this.render_editing_input(colIndex, value, parent);
		if (!control) return false;

		control.df.change = () => control.set_focus();

		return {
			initValue: (value) => {
				return control.set_value(value);
			},
			setValue: (value) => {
				const cell = this.datatable.getCell(colIndex, rowIndex);
				let fieldname = this.datatable.getColumn(colIndex).docfield.fieldname;
				let docname = cell.name;
				let doctype = cell.doctype;

				control.set_value(value);
				return this.set_control_value(doctype, docname, fieldname, value)
					.then((updated_doc) => {
						const _data = this.data.find(d => d.name === updated_doc.name);
						for (let field in _data) {
							_data[field] = updated_doc[field];
						}
					})
					.then(() => this.refresh_charts());
			},
			getValue: () => {
				return control.get_value();
			}
		};
	}

	set_control_value(doctype, docname, fieldname, value) {
		this.last_updated_doc = docname;
		return new Promise((resolve, reject) => {
			frappe.db.set_value(doctype, docname, {[fieldname]: value})
				.then(r => {
					if (r.message) {
						resolve(r.message);
					} else {
						reject();
					}
				})
				.fail(reject);
		});
	}

	render_editing_input(colIndex, value, parent) {
		const col = this.datatable.getColumn(colIndex);
		let control = null;

		if (col.docfield.fieldtype === 'Text Editor') {
			const d = new frappe.ui.Dialog({
				title: __('Edit {0}', [col.docfield.label]),
				fields: [col.docfield],
				primary_action: () => {
					this.datatable.cellmanager.submitEditing();
					this.datatable.cellmanager.deactivateEditing();
					d.hide();
				}
			});
			d.show();
			control = d.fields_dict[col.docfield.fieldname];
		} else {
			// make control
			control = frappe.ui.form.make_control({
				df: col.docfield,
				parent: parent,
				render_input: true
			});
			control.set_value(value);
			control.toggle_label(false);
			control.toggle_description(false);
		}

		return control;
	}

	is_editable(df, data) {
		if (!df || data.docstatus !== 0) return false;
		const is_standard_field = frappe.model.std_fields_list.includes(df.fieldname);
		const can_edit = !(
			is_standard_field
			|| df.read_only
			|| df.hidden
			|| !frappe.model.can_write(this.doctype)
		);
		return can_edit;
	}

	get_data(values) {
		return this.build_rows(values);
	}

	set_fields() {
		if (this.report_name && this.report_doc.json.fields) {
			this.fields = this.report_doc.json.fields.slice();
			return;
		} else if (this.view_user_settings.fields) {
			// get from user_settings
			this.fields = this.view_user_settings.fields;
			return;
		}

		// get fields from meta
		this.fields = [];
		const add_field = f => this._add_field(f);

		// default fields
		[
			'name', 'docstatus',
			this.meta.title_field,
			this.meta.image_field
		].map(add_field);

		// fields in_list_view or in_standard_filter
		const fields = this.meta.fields.filter(df => {
			return (df.in_list_view || df.in_standard_filter)
				&& frappe.perm.has_perm(this.doctype, df.permlevel, 'read')
				&& frappe.model.is_value_type(df.fieldtype)
				&& !df.report_hide;
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

		// fields in listview_settings
		(this.settings.add_fields || []).map(add_field);
	}

	build_fields() {
		this.fields.push(['docstatus', this.doctype]);
		super.build_fields();
	}

	get_fields() {
		let fields = this.fields.map(f => {
			let column_name = frappe.model.get_full_column_name(f[0], f[1]);
			if (f[1] !== this.doctype) {
				// child table field
				column_name = column_name + ' as ' + `'${f[1]}:${f[0]}'`;
			}
			return column_name;
		});
		const cdt_name_fields =
			this.get_unique_cdt_in_view()
				.map(cdt => frappe.model.get_full_column_name('name', cdt) + ' as ' + `'${cdt}:name'`);
		fields = fields.concat(cdt_name_fields);

		return fields;
	}

	get_unique_cdt_in_view() {
		return this.fields
			.filter(f => f[1] !== this.doctype)
			.map(f => f[1])
			.uniqBy(d => d);
	}

	add_column_to_datatable(fieldname, doctype, col_index) {
		const field = [fieldname, doctype];
		this.fields.splice(col_index, 0, field);

		this.add_currency_column(fieldname, doctype, col_index);

		this.build_fields();
		this.setup_columns();

		this.datatable.destroy();
		this.datatable = null;
		this.refresh();
	}

	add_currency_column(fieldname, doctype, col_index) {
		// Adds dependent currency field if required
		const df = frappe.meta.get_docfield(doctype, fieldname);
		if (df && df.fieldtype === 'Currency' && df.options &&
			!df.options.includes(':') && frappe.meta.has_field(doctype, df.options)
		) {
			const field = [df.options, doctype];
			if (col_index === undefined) {
				this.fields.push(field);
			} else {
				this.fields.splice(col_index, 0, field);
			}
			frappe.show_alert(__('Also adding the dependent currency field {0}', [field[0].bold()]));
		}
	}

	remove_column_from_datatable(column) {
		const index = this.fields.findIndex(f => column.field === f[0]);
		if (index === -1) return;
		const field = this.fields[index];
		if (field[0] === 'name') {
			this.refresh();
			frappe.throw(__('Cannot remove ID field'));
		}
		this.fields.splice(index, 1);
		this.build_fields();
		this.setup_columns();
		this.refresh();
	}

	switch_column(col1, col2) {
		const index1 = this.fields.findIndex(f => col1.field === f[0]);
		const index2 = this.fields.findIndex(f => col2.field === f[0]);
		const _fields = this.fields.slice();

		let temp = _fields[index1];
		_fields[index1] = _fields[index2];
		_fields[index2] = temp;

		this.fields = _fields;
		this.build_fields();
		this.setup_columns();
		this.refresh();
	}

	get_columns_for_picker() {
		let out = {};

		const standard_fields_filter = df =>
			!in_list(frappe.model.no_value_type, df.fieldtype) &&
			!df.report_hide && df.fieldname !== 'naming_series' &&
			!df.hidden;

		let doctype_fields = frappe.meta.get_docfields(this.doctype).filter(standard_fields_filter);

		doctype_fields = [{
			label: __('ID'),
			fieldname: 'name',
			fieldtype: 'Data'
		}].concat(doctype_fields, frappe.model.std_fields);

		out[this.doctype] = doctype_fields;

		const table_fields = frappe.meta.get_table_fields(this.doctype)
			.filter(df => !df.hidden);

		table_fields.forEach(df => {
			const cdt = df.options;
			const child_table_fields = frappe.meta.get_docfields(cdt).filter(standard_fields_filter);

			out[cdt] = child_table_fields;
		});

		return out;
	}

	get_dialog_fields() {
		const dialog_fields = [];
		const columns = this.get_columns_for_picker();

		dialog_fields.push({
			label: __(this.doctype),
			fieldname: this.doctype,
			fieldtype: 'MultiCheck',
			columns: 2,
			options: columns[this.doctype]
				.map(df => ({
					label: __(df.label),
					value: df.fieldname,
					checked: this.fields.find(f => f[0] === df.fieldname)
				}))
		});

		delete columns[this.doctype];

		const table_fields = frappe.meta.get_table_fields(this.doctype)
			.filter(df => !df.hidden);

		table_fields.forEach(df => {
			const cdt = df.options;

			dialog_fields.push({
				label: __(df.label) + ` (${__(cdt)})`,
				fieldname: df.options,
				fieldtype: 'MultiCheck',
				columns: 2,
				options: columns[cdt]
					.map(df => ({
						label: __(df.label),
						value: df.fieldname,
						checked: this.fields.find(f => f[0] === df.fieldname && f[1] === cdt)
					}))
			});
		});

		return dialog_fields;
	}

	is_column_added(df) {
		return Boolean(
			this.fields.find(f => f[0] === df.fieldname && df.parent === f[1])
		);
	}

	setup_columns() {
		const hide_columns = ['docstatus'];
		const fields = this.fields.filter(f => !hide_columns.includes(f[0]));
		this.columns = fields.map(f => this.build_column(f)).filter(Boolean);
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

		let title = __(docfield ? docfield.label : toTitle(fieldname));
		if (doctype !== this.doctype) {
			title += ` (${__(doctype)})`;
		}

		const editable = frappe.model.is_non_std_field(fieldname) && !docfield.read_only;

		const align = (() => {
			const is_numeric = frappe.model.is_numeric_field(docfield);
			if (is_numeric) {
				return 'right';
			}
			return docfield.fieldtype === 'Date' ? 'right' : 'left';
		})();

		const width = (docfield ? cint(docfield.width) : null) || null;

		// child table column
		const id = doctype !== this.doctype ? `${doctype}:${fieldname}` : fieldname;

		let compareFn = null;
		if (docfield.fieldtype === 'Date') {
			compareFn = (cell, keyword) => {
				if (!cell.content) return null;
				if (keyword.length !== 'YYYY-MM-DD'.length) return null;

				const keywordValue = frappe.datetime.user_to_obj(keyword);
				const cellValue = frappe.datetime.str_to_obj(cell.content);
				return [+cellValue, +keywordValue];
			}
		}


		return {
			id: id,
			field: fieldname,
			name: title,
			content: title,
			docfield,
			width,
			editable,
			align,
			compareValue: compareFn,
			format: (value, row, column, data) => {
				const d = row.reduce((acc, curr) => {
					if (!curr.column.docfield) return acc;
					acc[curr.column.docfield.fieldname] = curr.content;
					return acc;
				}, {});

				return frappe.format(value, column.docfield, { always_show_decimals: true }, d);
			}
		};
	}

	build_rows(data) {
		const out = data.map(d => this.build_row(d));

		if (this.add_totals_row) {
			const totals = this.get_columns_totals(data);
			const totals_row = this.columns.map((col, i) => {
				return {
					name: __('Totals Row'),
					content: totals[col.id],
					format: value => {
						return frappe.format(value, col.docfield, { always_show_decimals: true });
					}
				}
			})

			totals_row[0].content = __('Totals').bold();
			out.push(totals_row);
		}

		return out;
	}

	build_row(d) {
		return this.columns.map(col => {
			if (col.docfield.parent !== this.doctype) {
				// child table field
				const cdt_field = f => `${col.docfield.parent}:${f}`;
				const name = d[cdt_field('name')];

				return {
					name: name,
					doctype: col.docfield.parent,
					content: d[cdt_field(col.field)],
					editable: Boolean(name && this.is_editable(col.docfield, d)),
					format: value => {
						return frappe.format(value, col.docfield, { always_show_decimals: true });
					}
				};
			}

			if (col.field in d) {
				const value = d[col.field];
				return {
					name: d.name,
					doctype: col.docfield.parent,
					content: value,
					editable: this.is_editable(col.docfield, d)
				};
			}
			return {
				content: ''
			};
		});
	}

	get_checked_items(only_docnames) {
		const indexes = this.datatable.rowmanager.getCheckedRows();
		const items = indexes.filter(i => i != undefined)
			.map(i => this.data[i]);

		if (only_docnames) {
			return items.map(d => d.name);
		}

		return items;
	}

	save_report(save_type) {
		const _save_report = (name) => {
			// callback
			const report_settings = {
				filters: this.filter_area.get(),
				fields: this.fields,
				order_by: this.sort_selector.get_sql_string(),
				add_totals_row: this.add_totals_row,
				page_length: this.page_length
			}

			return frappe.call({
				method: 'frappe.desk.reportview.save_report',
				args: {
					name: name,
					doctype: this.doctype,
					json: JSON.stringify(report_settings)
				},
				callback:(r) => {
					if(r.exc) {
						frappe.msgprint(__("Report was not saved (there were errors)"));
						return;
					}
					if(r.message != this.report_name) {
						// Rerender the reports dropdown,
						// so that this report is included in the dropdown as well.
						frappe.boot.user.all_reports[r.message] = {
							ref_doctype: "Item",
							report_type: "Report Builder",
							title: r.message,
						};
						this.list_sidebar.setup_reports();
						frappe.set_route('List', this.doctype, 'Report', r.message);
					}

					// update state
					this.report_doc.json = report_settings;
					this.set_dirty_state_for_custom_report();
				}
			});

		};

		if(this.report_name && save_type == "save") {
			_save_report(this.report_name);
		} else {
			frappe.prompt({fieldname: 'name', label: __('New Report name'), reqd: 1, fieldtype: 'Data'}, (data) => {
				_save_report(data.name);
			}, __('Save As'));
		}
	}

	get_report_doc() {
		return new Promise(resolve => {
			frappe.model.with_doc('Report', this.report_name, () => {
				resolve(frappe.get_doc('Report', this.report_name));
			});
		});
	}

	get_filters_html_for_print() {
		const filters = this.filter_area.get();

		return filters.map(f => {
			const [doctype, fieldname, condition, value] = f;
			if (condition !== '=') return '';

			const label = frappe.meta.get_label(doctype, fieldname);
			return `<h6>${__(label)}: ${value}</h6>`;
		}).join('');
	}

	get_columns_totals(data) {
		if (!this.add_totals_row) {
			return [];
		}

		const row_totals = {};

		this.columns.forEach((col, i) => {
			const totals = data.reduce((totals, d) => {
				if (col.id in d && frappe.model.is_numeric_field(col.docfield)) {
					totals += flt(d[col.id]);
					return totals;
				}
			}, 0);

			row_totals[col.id] = totals;
		});

		return row_totals;
	}

	report_menu_items() {
		let items = [
			{
				label: __('Show Totals'),
				action: () => {
					this.add_totals_row = !this.add_totals_row;
					this.save_view_user_settings({ add_totals_row: this.add_totals_row });
					this.datatable.refresh(this.get_data(this.data));
				}
			},
			{
				label: __('Print'),
				action: () => {
					this.report_data = this.data.slice();

					if (this.add_totals_row) {
						const total_data = this.get_columns_totals(this.data);

						total_data['name'] = __('Totals').bold();
						this.report_data.push(total_data);
					}

					frappe.ui.get_print_settings(false, (print_settings) => {
						var title =  __(this.doctype);
						frappe.render_grid({
							title: title,
							subtitle: this.get_filters_html_for_print(),
							print_settings: print_settings,
							columns: this.columns,
							data: this.report_data
						});
					});
				}
			},
			{
				label: __('Toggle Chart'),
				action: () => this.toggle_charts()
			},
			{
				label: __('Toggle Sidebar'),
				action: () => this.toggle_side_bar()
			},
			{
				label: __('Pick Columns'),
				action: () => {
					const d = new frappe.ui.Dialog({
						title: __('Pick Columns'),
						fields: this.get_dialog_fields(),
						primary_action: (values) => {
							// doctype fields
							let fields = values[this.doctype].map(f => [f, this.doctype]);
							delete values[this.doctype];

							// child table fields
							for (let cdt in values) {
								fields = fields.concat(values[cdt].map(f => [f, cdt]));
							}

							// always keep name (ID) column
							this.fields = [["name", this.doctype], ...fields];

							this.fields.map(f => this.add_currency_column(f[0], f[1]));

							this.build_fields();
							this.setup_columns();

							this.datatable.destroy();
							this.datatable = null;
							this.refresh();

							d.hide();
						}
					});

					d.show();
				}
			}
		];

		if (frappe.model.can_export(this.doctype)) {
			items.push({
				label: __('Export'),
				action: () => {
					const args = this.get_args();
					const selected_items = this.get_checked_items(true);

					const d = new frappe.ui.Dialog({
						title: __("Export Report: {0}",[__(this.doctype)]),
						fields: [
							{
								fieldtype: 'Select',
								label: __('Select File Type'),
								fieldname:'file_format_type',
								options: ['Excel', 'CSV'],
								default: 'Excel'
							},
							{
								fieldtype: 'Check',
								fieldname: 'export_all_rows',
								label: __('Export All {0} rows?', [(this.total_count + "").bold()])
							}
						],
						primary_action_label: __('Download'),
						primary_action: (data) => {
							args.cmd = 'frappe.desk.reportview.export_query';
							args.file_format_type = data.file_format_type;

							if(this.add_totals_row) {
								args.add_totals_row = 1;
							}

							if(selected_items.length > 0) {
								args.selected_items = selected_items;
							}

							if (!data.export_all_rows) {
								args.start = 0;
								args.page_length = this.data.length;
							} else {
								delete args.start;
								delete args.page_length;
							}

							open_url_post(frappe.request.url, args);

							d.hide();
						},
					});

					d.show();
				}
			});
		}

		items.push({
			label: __("Setup Auto Email"),
			action: () => {
				if(this.report_name) {
					frappe.set_route('List', 'Auto Email Report', {'report' : this.report_name});
				} else {
					frappe.msgprint(__('Please save the report first'));
				}
			}
		});

		// save buttons
		if(frappe.user.is_report_manager()) {
			items = items.concat([
				{ label: __('Save'), action: () => this.save_report('save') },
				{ label: __('Save As'), action: () => this.save_report('save_as') }
			]);
		}

		// user permissions
		if(this.report_name && frappe.model.can_set_user_permissions("Report")) {
			items.push({
				label: __("User Permissions"),
				action: () => {
					const args = {
						doctype: "Report",
						name: this.report_name
					};
					frappe.set_route('List', 'User Permission', args);
				}
			});
		}

		// add to desktop
		items.push({
			label: __('Add to Desktop'),
			action: () => {
				frappe.add_to_desktop(
					this.report_name || __('{0} Report', [this.doctype]),
					this.doctype, this.report_name
				);
			}
		});

		return items.map(i => Object.assign(i, { standard: true }));
	}

};
