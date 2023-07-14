/**
 * frappe.views.ReportView
 */
import DataTable from "frappe-datatable";

window.DataTable = DataTable;
frappe.provide("frappe.views");

frappe.views.ReportView = class ReportView extends frappe.views.ListView {
	get view_name() {
		return "Report";
	}

	render_header() {
		// Override List View Header
	}

	setup_defaults() {
		super.setup_defaults();
		this.page_title = __("Report:") + " " + this.page_title;
		this.view = "Report";

		const route = frappe.get_route();
		if (route.length === 4) {
			this.report_name = route[3];
		}

		if (this.report_name) {
			return this.get_report_doc().then((doc) => {
				this.report_doc = doc;
				this.report_doc.json = JSON.parse(this.report_doc.json);

				this.filters = this.report_doc.json.filters;
				this.order_by = this.report_doc.json.order_by;
				this.add_totals_row = this.report_doc.json.add_totals_row;
				this.page_title = __(this.report_name);
				this.page_length = this.report_doc.json.page_length || 20;
				this.order_by = this.report_doc.json.order_by || "modified desc";
				this.chart_args = this.report_doc.json.chart_args;
			});
		} else {
			this.add_totals_row = this.view_user_settings.add_totals_row || 0;
			this.chart_args = this.view_user_settings.chart_args;
		}
		return this.get_list_view_settings();
	}

	setup_view() {
		this.setup_columns();
		super.setup_new_doc_event();
		this.setup_events();
		this.page.main.addClass("report-view");
	}

	setup_events() {
		if (this.list_view_settings?.disable_auto_refresh) {
			return;
		}
		frappe.socketio.doctype_subscribe(this.doctype);
		frappe.realtime.on("list_update", (data) => this.on_update(data));
	}

	setup_page() {
		this.menu_items = this.report_menu_items();
		super.setup_page();
	}

	toggle_side_bar() {
		super.toggle_side_bar();
		// refresh datatable when sidebar is toggled to accomodate extra space
		this.render(true);
	}

	setup_result_area() {
		super.setup_result_area();
		this.setup_charts_area();
		this.$datatable_wrapper = $('<div class="datatable-wrapper">');
		this.$result.append(this.$datatable_wrapper);
	}

	setup_charts_area() {
		this.$charts_wrapper = $(`<div class="charts-wrapper hidden">
			<div class="text-right"><button class="btn btn-default btn-xs btn-chart-configure"
				style="margin-right: 15px; margin-top: 15px">Configure</button></div>
			<div class="charts-inner-wrapper"></div>
		</div>`);
		this.$result.append(this.$charts_wrapper);
		this.$charts_wrapper.find(".btn-chart-configure").on("click", () => {
			this.setup_charts();
		});
	}

	setup_paging_area() {
		super.setup_paging_area();
		const message = __(
			"For comparison, use >5, <10 or =324. For ranges, use 5:10 (for values between 5 & 10)."
		);
		this.$paging_area
			.find(".level-left")
			.append(`<span class="comparison-message text-muted">${message}</span>`);
	}

	setup_sort_selector() {
		this.sort_selector = new frappe.ui.SortSelector({
			parent: this.filter_area.$filter_list_wrapper,
			doctype: this.doctype,
			args: this.order_by,
			onchange: this.on_sort_change.bind(this),
		});

		//Setup groupby for reports
		this.group_by_control = new frappe.ui.GroupBy(this);
		if (this.report_doc && this.report_doc.json.group_by) {
			this.group_by_control.apply_settings(this.report_doc.json.group_by);
		}
		if (this.view_user_settings && this.view_user_settings.group_by) {
			this.group_by_control.apply_settings(this.view_user_settings.group_by);
		}
	}

	get_args() {
		const args = super.get_args();
		delete args.group_by;
		this.group_by_control.set_args(args);

		return args;
	}

	before_refresh() {
		if (this.report_doc) {
			// don't parse frappe.route_options if this is a Custom Report
			return Promise.resolve();
		}
		return super.before_refresh();
	}

	after_render() {
		if (!this.report_doc) {
			this.save_report_settings();
		} else if (!$.isEmptyObject(this.report_doc.json)) {
			this.set_dirty_state_for_custom_report();
		}

		if (!this.group_by) {
			this.init_chart();
		}
	}

	set_dirty_state_for_custom_report() {
		let current_settings = {
			filters: this.filter_area.get(),
			fields: this.fields,
			order_by: this.sort_selector.get_sql_string(),
			add_totals_row: this.add_totals_row,
			page_length: this.page_length,
			column_widths: this.get_column_widths(),
			group_by: this.group_by_control.get_settings(),
			chart_args: this.get_chart_settings(),
		};

		let report_settings = {
			filters: this.report_doc.json.filters,
			fields: this.report_doc.json.fields,
			order_by: this.report_doc.json.order_by,
			add_totals_row: this.report_doc.json.add_totals_row,
			page_length: this.report_doc.json.page_length,
			column_widths: this.report_doc.json.column_widths,
			group_by: this.report_doc.json.group_by,
			chart_args: this.report_doc.json.chart_args,
		};

		if (!frappe.utils.deep_equal(current_settings, report_settings)) {
			this.page.set_indicator(__("Not Saved"), "orange");
		} else {
			this.page.clear_indicator();
		}
	}

	save_report_settings() {
		frappe.model.user_settings.save(this.doctype, "last_view", this.view_name);

		if (!this.report_name) {
			this.save_view_user_settings({
				fields: this.fields,
				filters: this.filter_area.get(),
				order_by: this.sort_selector.get_sql_string(),
				group_by: this.group_by_control.get_settings(),
				chart_args: this.get_chart_settings(),
				add_totals_row: this.add_totals_row,
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
		this.setup_columns();

		if (this.group_by) {
			this.$charts_wrapper.addClass("hidden");
		} else if (this.chart) {
			this.refresh_charts();
		}

		if (this.datatable && !force) {
			this.datatable.refresh(this.get_data(this.data), this.columns);
			return;
		}
		this.setup_datatable(this.data);
	}

	render_count() {
		if (this.list_view_settings?.disable_count) {
			return;
		}
		let $list_count = this.$paging_area.find(".list-count");
		if (!$list_count.length) {
			$list_count = $("<span>")
				.addClass("text-muted list-count")
				.prependTo(this.$paging_area.find(".level-right"));
		}
		this.get_count_str().then((str) => {
			$list_count.text(str);
		});
	}

	on_update(data) {
		if (this.doctype === data.doctype && data.name) {
			// flash row when doc is updated by some other user
			const flash_row = data.user !== frappe.session.user;
			if (this.data.find((d) => d.name === data.name)) {
				// update existing
				frappe.db
					.get_doc(data.doctype, data.name)
					.then((doc) => this.update_row(doc, flash_row));
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
					if (fieldname.includes(":")) {
						// child table field
						const [cdt, _field] = fieldname.split(":");
						const cdt_row = Object.keys(doc)
							.filter(
								(key) =>
									Array.isArray(doc[key]) &&
									doc[key].length &&
									doc[key][0].doctype === cdt
							)
							.map((key) => doc[key])
							.map((a) => a[0])
							.filter((cdoc) => cdoc.name === d[cdt + ":name"])[0];
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
			$row.addClass("row-update");
			setTimeout(() => $row.removeClass("row-update"), 500);
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
			language: frappe.boot.lang,
			translations: frappe.utils.datatable.get_translations(),
			checkboxColumn: true,
			inlineFilters: true,
			cellHeight: 35,
			direction: frappe.utils.is_rtl() ? "rtl" : "ltr",
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
				},
			},
			hooks: {
				columnTotal: frappe.utils.report_column_total,
			},
			headerDropdown: [
				{
					label: __("Add Column"),
					action: (datatabe_col) => {
						let columns_in_picker = [];
						const columns = this.get_columns_for_picker();

						columns_in_picker = columns[this.doctype]
							.filter((df) => !this.is_column_added(df))
							.map((df) => ({
								label: __(df.label),
								value: df.fieldname,
							}));

						delete columns[this.doctype];

						for (let cdt in columns) {
							columns[cdt]
								.filter((df) => !this.is_column_added(df))
								.map((df) => ({
									label: __(df.label) + ` (${cdt})`,
									value: df.fieldname + "," + cdt,
								}))
								.forEach((df) => columns_in_picker.push(df));
						}

						const d = new frappe.ui.Dialog({
							title: __("Add Column"),
							fields: [
								{
									label: __("Select Column"),
									fieldname: "column",
									fieldtype: "Autocomplete",
									options: columns_in_picker,
								},
								{
									label: __("Insert Column Before {0}", [
										__(datatabe_col.docfield.label).bold(),
									]),
									fieldname: "insert_before",
									fieldtype: "Check",
								},
							],
							primary_action: ({ column, insert_before }) => {
								if (!columns_in_picker.map((col) => col.value).includes(column)) {
									frappe.show_alert({
										message: __("Invalid column"),
										indicator: "orange",
									});
									d.hide();
									return;
								}

								let doctype = this.doctype;
								if (column.includes(",")) {
									[column, doctype] = column.split(",");
								}

								let index = datatabe_col.colIndex;
								if (insert_before) {
									index = index - 1;
								}

								this.add_column_to_datatable(column, doctype, index);
								d.hide();
							},
						});

						d.show();
					},
				},
			],
		});
	}

	toggle_charts() {
		// add
		if (!this.chart) {
			this.setup_charts();
			return;
		}

		if (this.$charts_wrapper.hasClass("hidden")) {
			// reload chart
			this.$charts_wrapper.removeClass("hidden");
			this.refresh_charts();
		} else {
			// remove chart
			this.$charts_wrapper.addClass("hidden");
			this.save_view_user_settings({ chart_args: null });
			this.chart_args = null;
		}
	}

	init_chart() {
		// show chart if saved via report or user settings
		if (!this.chart) {
			if (this.chart_args) {
				this.build_chart_args(
					this.chart_args.x_axis,
					this.chart_args.y_axes,
					this.chart_args.chart_type
				);

				this.make_chart();
			}
		}
	}

	setup_charts() {
		// get fields from columns
		let x_fields = [],
			y_fields = [];
		for (let col of this.columns) {
			// all options in x
			x_fields.push({
				label: col.content,
				fieldname: col.id,
				value: col.id,
			});

			// numeric values in y
			if (col.docfield && frappe.model.numeric_fieldtypes.includes(col.docfield.fieldtype)) {
				y_fields.push({
					label: col.content,
					fieldname: col.id,
					value: col.id,
				});
			}
		}

		const defaults = this.chart_args || {};

		const dialog = new frappe.ui.Dialog({
			title: __("Configure Chart"),
			fields: [
				{
					label: __("X Axis Field"),
					fieldtype: "Select",
					fieldname: "x_axis",
					options: x_fields,
					default: defaults.x_axis,
				},
				{
					label: __("Y Axis Fields"),
					fieldtype: "MultiSelect",
					fieldname: "y_axes",
					options: y_fields,
					description: __("Showing only Numeric fields from Report"),
					default: defaults.y_axes ? defaults.y_axes.join(", ") : null,
				},
				{
					label: __("Chart Type"),
					fieldtype: "Select",
					options: ["Bar", "Line", "Pie", "Percentage", "Donut"],
					fieldname: "chart_type",
					default: defaults.chart_type
						? frappe.utils.to_title_case(defaults.chart_type)
						: "Bar",
				},
			],
			primary_action: (data) => {
				data.y_axes = data.y_axes
					.split(",")
					.map((d) => d.trim())
					.filter(Boolean);

				this.build_chart_args(data.x_axis, data.y_axes, data.chart_type);
				this.make_chart();
				dialog.hide();
			},
		});

		dialog.show();
	}

	build_chart_args(x_axis, y_axes, chart_type) {
		let datasets = y_axes.map((y_axis) => ({
			name: this.columns_map[y_axis].content,
			values: this.data.map((d) => d[y_axis]),
		}));

		this.chart_args = {
			chart_type: chart_type.toLowerCase(),
			x_axis: x_axis,
			y_axes: y_axes,
			labels: this.data.map((d) => d[x_axis]),
			datasets: datasets,
		};

		this.save_view_user_settings({ chart_args: this.get_chart_settings() });
	}

	get_chart_settings() {
		if (this.chart_args) {
			return {
				chart_type: this.chart_args.chart_type,
				x_axis: this.chart_args.x_axis,
				y_axes: this.chart_args.y_axes,
			};
		}
	}

	make_chart() {
		const args = this.chart_args;
		let data = {
			labels: args.labels,
			datasets: args.datasets,
		};

		this.last_chart_type = args.chart_type;

		const get_df = (field) => this.columns_map[field].docfield;

		this.$charts_wrapper.removeClass("hidden");

		this.chart = new frappe.Chart(this.$charts_wrapper.find(".charts-inner-wrapper")[0], {
			title: __("{0} Chart", [this.doctype]),
			data: data,
			type: args.chart_type,
			truncateLegends: 1,
			colors: ["#70E078", "light-blue", "orange", "red"],
			axisOptions: {
				shortenYAxisNumbers: 1,
				numberFormatter: frappe.utils.format_chart_axis_number,
			},
			tooltipOptions: {
				formatTooltipY: (value) => {
					return frappe.format(value, get_df(this.chart_args.y_axes[0]), {
						always_show_decimals: true,
						inline: true,
					});
				},
			},
		});
	}

	refresh_charts() {
		if (!this.chart || !this.chart_args) return;
		this.$charts_wrapper.removeClass("hidden");
		const { x_axis, y_axes, chart_type } = this.chart_args;
		this.build_chart_args(x_axis, y_axes, chart_type);
		this.chart.update(this.chart_args);
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
						const _data = this.data
							.filter((b) => b.name === updated_doc.name)
							.find(
								(a) =>
									// child table cell
									(doctype != updated_doc.doctype &&
										a[doctype + ":name"] == docname) ||
									doctype == updated_doc.doctype
							);

						for (let field in _data) {
							if (field.includes(":")) {
								// child table field
								const [cdt, _field] = field.split(":");
								const cdt_row = Object.keys(updated_doc)
									.filter(
										(key) =>
											Array.isArray(updated_doc[key]) &&
											updated_doc[key].length &&
											updated_doc[key][0].doctype === cdt
									)
									.map((key) => updated_doc[key])[0]
									.filter((cdoc) => cdoc.name === _data[cdt + ":name"])[0];
								if (cdt_row) {
									_data[field] = cdt_row[_field];
								}
							} else {
								_data[field] = updated_doc[field];
							}
						}
					})
					.then(() => this.refresh_charts());
			},
			getValue: () => {
				return control.get_value();
			},
		};
	}

	set_control_value(doctype, docname, fieldname, value) {
		this.last_updated_doc = docname;
		return new Promise((resolve, reject) => {
			frappe.db
				.set_value(doctype, docname, { [fieldname]: value })
				.then((r) => {
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

		if (col.docfield.fieldtype === "Text Editor") {
			const d = new frappe.ui.Dialog({
				title: __("Edit {0}", [col.docfield.label]),
				fields: [col.docfield],
				primary_action: () => {
					this.datatable.cellmanager.deactivateEditing();
					d.hide();
				},
				on_hide: () => {
					this.datatable.cellmanager.deactivateEditing(false);
				},
			});
			d.show();
			control = d.fields_dict[col.docfield.fieldname];
		} else {
			// make control
			control = frappe.ui.form.make_control({
				df: col.docfield,
				parent: parent,
				render_input: true,
			});
			control.set_value(value);
			control.toggle_label(false);
			control.toggle_description(false);
		}

		return control;
	}

	is_editable(df, data) {
		if (
			df &&
			frappe.model.can_write(this.doctype) &&
			// not a submitted doc or field is allowed to edit after submit
			(data.docstatus !== 1 || df.allow_on_submit) &&
			// not a cancelled doc
			data.docstatus !== 2 &&
			!df.read_only &&
			!df.is_virtual &&
			!df.hidden &&
			// not a standard field i.e., owner, modified_by, etc.
			frappe.model.is_non_std_field(df.fieldname)
		)
			return true;
		return false;
	}

	get_data(values) {
		return this.build_rows(values);
	}

	set_fields() {
		// default fields
		["name", "docstatus"].map((f) => this._add_field(f));

		if (this.report_name && this.report_doc.json.fields) {
			let fields = this.report_doc.json.fields.slice();
			fields.forEach((f) => this._add_field(f[0], f[1]));
			return;
		} else if (this.view_user_settings.fields) {
			// get from user_settings
			let fields = this.view_user_settings.fields;
			fields.forEach((f) => this._add_field(f[0], f[1]));
			return;
		}

		this.set_default_fields();
	}

	set_default_fields() {
		// get fields from meta
		this.fields = this.fields || [];
		const add_field = (f) => this._add_field(f);

		// default fields
		[this.meta.title_field, this.meta.image_field].map(add_field);

		// fields in_list_view or in_standard_filter
		const fields = this.meta.fields.filter((df) => {
			return (
				(df.in_list_view || df.in_standard_filter) &&
				frappe.perm.has_perm(this.doctype, df.permlevel, "read") &&
				frappe.model.is_value_type(df.fieldtype) &&
				!df.report_hide
			);
		});

		fields.map(add_field);

		// currency fields
		fields
			.filter((df) => df.fieldtype === "Currency" && df.options)
			.map((df) => {
				if (df.options.includes(":")) {
					add_field(df.options.split(":")[1]);
				} else {
					add_field(df.options);
				}
			});

		// fields in listview_settings
		(this.settings.add_fields || []).map(add_field);
	}

	build_fields() {
		super.build_fields();
	}

	reorder_fields() {
		// generate table fields in the required format ["name", "DocType"]
		// these are fields in the column before adding new fields
		let table_fields = this.columns.map((df) => [df.field, df.docfield.parent]);

		// filter fields that are already in table
		// iterate over table_fields to preserve the existing order of fields
		// The filter will ensure the unchecked fields are removed
		let fields_already_in_table = table_fields.filter((df) => {
			return this.fields.find((field) => {
				return df[0] == field[0] && df[1] == field[1];
			});
		});

		// find new fields that didn't already exists
		// This will be appended to the end of the table
		let fields_to_add = this.fields.filter((df) => {
			return !table_fields.find((field) => {
				return df[0] == field[0] && df[1] == field[1];
			});
		});

		// rebuild fields
		this.fields = [...fields_already_in_table, ...fields_to_add];
	}

	get_fields() {
		let fields = this.fields.map((f) => {
			let column_name = frappe.model.get_full_column_name(f[0], f[1]);
			if (f[1] !== this.doctype) {
				// child table field
				column_name = column_name + " as " + `'${f[1]}:${f[0]}'`;
			}
			return column_name;
		});
		const cdt_name_fields = this.get_unique_cdt_in_view().map(
			(cdt) => frappe.model.get_full_column_name("name", cdt) + " as " + `'${cdt}:name'`
		);
		fields = fields.concat(cdt_name_fields);

		return fields;
	}

	get_unique_cdt_in_view() {
		return this.fields
			.filter((f) => f[1] !== this.doctype)
			.map((f) => f[1])
			.uniqBy((d) => d);
	}

	add_column_to_datatable(fieldname, doctype, col_index) {
		const field = [fieldname, doctype];
		this.fields.splice(col_index, 0, field);

		this.add_currency_column(fieldname, doctype, col_index);

		this.build_fields();
		this.setup_columns();

		if (this.datatable) this.datatable.destroy();
		this.datatable = null;
		this.refresh();
	}

	add_currency_column(fieldname, doctype, col_index) {
		// Adds dependent currency field if required
		const df = frappe.meta.get_docfield(doctype, fieldname);
		if (
			df &&
			df.fieldtype === "Currency" &&
			df.options &&
			!df.options.includes(":") &&
			frappe.meta.has_field(doctype, df.options)
		) {
			const field = [df.options, doctype];
			if (col_index === undefined) {
				this.fields.push(field);
			} else {
				this.fields.splice(col_index, 0, field);
			}
			const field_label = frappe.meta.get_label(doctype, field[0]);
			frappe.show_alert(
				__("Also adding the dependent currency field {0}", [__(field_label).bold()])
			);
		}
	}

	add_status_dependency_column(col, doctype) {
		// Adds dependent column from which status is derived if required
		if (col && !this.fields.find((f) => f[0] === col)) {
			const field = [col, doctype];
			this.fields.push(field);
			this.refresh();
			const field_label = frappe.meta.get_label(doctype, field[0]);
			frappe.show_alert(
				__("Also adding the status dependency field {0}", [__(field_label).bold()])
			);
		}
	}

	remove_column_from_datatable(column) {
		const index = this.fields.findIndex((f) => column.field === f[0]);
		if (index === -1) return;
		const field = this.fields[index];

		if (field[0] === "name") {
			this.refresh();
			frappe.throw(__("Cannot remove ID field"));
		}

		this.fields.splice(index, 1);
		this.build_fields();
		this.setup_columns();
		this.refresh();
	}

	switch_column(col1, col2) {
		const index1 = this.fields.findIndex((f) => col1.field === f[0]);
		const index2 = this.fields.findIndex((f) => col2.field === f[0]);
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

		const standard_fields_filter = (df) => !in_list(frappe.model.no_value_type, df.fieldtype);

		let doctype_fields = frappe.meta
			.get_docfields(this.doctype)
			.filter(standard_fields_filter);

		// filter out docstatus field from picker
		let std_fields = frappe.model.std_fields.filter((df) => df.fieldname !== "docstatus");

		// add status field derived from docstatus, if status is not a standard field
		let has_status_values = false;

		if (this.data) {
			has_status_values = frappe.get_indicator(this.data[0], this.doctype);
		}

		if (!frappe.meta.has_field(this.doctype, "status") && has_status_values) {
			doctype_fields = [
				{
					label: __("Status"),
					fieldname: "docstatus",
					fieldtype: "Data",
				},
			].concat(doctype_fields);
		}

		doctype_fields = [
			{
				label: __("ID", null, "Label of name column in report"),
				fieldname: "name",
				fieldtype: "Data",
				reqd: 1,
			},
		].concat(doctype_fields, std_fields);

		out[this.doctype] = doctype_fields;

		const table_fields = frappe.meta.get_table_fields(this.doctype);

		table_fields.forEach((df) => {
			const cdt = df.options;
			const child_table_fields = frappe.meta
				.get_docfields(cdt)
				.filter(standard_fields_filter);

			out[cdt] = child_table_fields;

			// add index column for child tables
			out[cdt].push({
				label: __("Index"),
				fieldname: "idx",
				fieldtype: "Int",
				parent: cdt,
			});
		});
		return out;
	}

	get_dialog_fields() {
		const dialog_fields = [];
		const columns = this.get_columns_for_picker();

		dialog_fields.push({
			label: __(this.doctype),
			fieldname: this.doctype,
			fieldtype: "MultiCheck",
			columns: 2,
			options: columns[this.doctype]
				.filter((df) => {
					return !df.hidden && df.fieldname !== "name";
				})
				.map((df) => ({
					label: __(df.label),
					value: df.fieldname,
					checked: this.fields.find(
						(f) => f[0] === df.fieldname && f[1] === this.doctype
					),
				})),
		});

		delete columns[this.doctype];

		const table_fields = frappe.meta.get_table_fields(this.doctype).filter((df) => !df.hidden);

		table_fields.forEach((df) => {
			const cdt = df.options;

			dialog_fields.push({
				label: __(df.label) + ` (${__(cdt)})`,
				fieldname: df.options,
				fieldtype: "MultiCheck",
				columns: 2,
				options: columns[cdt]
					.filter((df) => {
						return !df.hidden;
					})
					.map((df) => ({
						label: __(df.label),
						value: df.fieldname,
						checked: this.fields.find((f) => f[0] === df.fieldname && f[1] === cdt),
					})),
			});
		});

		return dialog_fields;
	}

	is_column_added(df) {
		return Boolean(this.fields.find((f) => f[0] === df.fieldname && df.parent === f[1]));
	}

	setup_columns() {
		// apply previous column width
		let column_widths = null;
		if (this.columns) {
			column_widths = this.get_column_widths();
		}

		this.columns = [];
		this.columns_map = {};

		for (let f of this.fields) {
			let column;
			if (f[0] !== "docstatus") {
				column = this.build_column(f);
			} else {
				// if status is not in fields append status column derived from docstatus
				if (
					!this.fields.includes(["status", this.doctype]) &&
					!frappe.meta.has_field(this.doctype, "status")
				) {
					column = this.build_column(["docstatus", this.doctype]);
				}
			}

			if (column) {
				if (column_widths) {
					column.width = column_widths[column.id] || column.width || 120;
				}
				this.columns.push(column);
				this.columns_map[column.id] = column;
			}
		}
	}

	build_column(c) {
		let [fieldname, doctype] = c;
		let docfield = frappe.meta.docfield_map[doctype || this.doctype][fieldname];

		// group by column
		if (fieldname === "_aggregate_column") {
			docfield = this.group_by_control.get_group_by_docfield();
		}

		// child table index column
		if (fieldname === "idx" && doctype !== this.doctype) {
			docfield = {
				label: "Index",
				fieldtype: "Int",
				parent: doctype,
			};
		}

		if (!docfield) {
			docfield = frappe.model.get_std_field(fieldname, true);

			if (docfield) {
				if (!docfield.label) {
					docfield.label = toTitle(fieldname);
					if (docfield.label.includes("_")) {
						docfield.label = docfield.label.replace("_", " ");
					}
				}
				docfield.parent = this.doctype;
				if (fieldname == "name") {
					docfield.options = this.doctype;
				}
				if (fieldname == "docstatus" && !frappe.meta.has_field(this.doctype, "status")) {
					docfield.label = "Status";
					docfield.fieldtype = "Data";
					docfield.name = "status";
				}
			}
		}
		if (!docfield || docfield.report_hide) return;

		let title = __(docfield.label);
		if (doctype !== this.doctype) {
			title += ` (${__(doctype)})`;
		}

		const editable =
			frappe.model.is_non_std_field(fieldname) &&
			!docfield.read_only &&
			!docfield.is_virtual;

		const align = (() => {
			const is_numeric = frappe.model.is_numeric_field(docfield);
			if (is_numeric) {
				return "right";
			}
			return docfield.fieldtype === "Date" ? "right" : "left";
		})();

		let id = fieldname;

		// child table column
		if (doctype !== this.doctype && fieldname !== "_aggregate_column") {
			id = `${doctype}:${fieldname}`;
		}

		let width = (docfield ? cint(docfield.width) : null) || null;
		if (this.report_doc) {
			// load the user saved column width
			let saved_column_widths = this.report_doc.json.column_widths || {};
			width = saved_column_widths[id] || width;
		}

		let compareFn = null;
		if (docfield.fieldtype === "Date") {
			compareFn = (cell, keyword) => {
				if (!cell.content) return null;
				if (keyword.length !== "YYYY-MM-DD".length) return null;

				const keywordValue = frappe.datetime.user_to_obj(keyword);
				const cellValue = frappe.datetime.str_to_obj(cell.content);
				return [+cellValue, +keywordValue];
			};
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
				let doc = null;
				if (Array.isArray(row)) {
					doc = row.reduce((acc, curr) => {
						if (!curr.column.docfield) return acc;
						acc[curr.column.docfield.fieldname] = curr.content;
						return acc;
					}, {});
				} else {
					doc = row;
				}

				return frappe.format(value, column.docfield, { always_show_decimals: true }, doc);
			},
		};
	}

	build_rows(data) {
		const out = data.map((d) => this.build_row(d));

		if (this.add_totals_row) {
			const totals = this.get_columns_totals(data);
			const totals_row = this.columns.map((col, i) => {
				return {
					name: __("Totals Row"),
					content: totals[col.id],
					format: (value) => {
						let formatted_value = frappe.format(
							value,
							col.docfield,
							{
								always_show_decimals: true,
							},
							data[0]
						);
						if (i === 0) {
							return this.format_total_cell(formatted_value, col);
						}
						return formatted_value;
					},
				};
			});

			out.push(totals_row);
		}
		return out;
	}

	format_total_cell(formatted_value, df) {
		let cell_value = __("Totals").bold();
		if (frappe.model.is_numeric_field(df.docfield)) {
			cell_value = `<span class="flex justify-between">
				${cell_value} ${$(formatted_value).text()}
			</span>`;
		}
		return cell_value;
	}

	build_row(d) {
		return this.columns.map((col) => {
			if (col.docfield.parent !== this.doctype) {
				// child table field
				const cdt_field = (f) => `${col.docfield.parent}:${f}`;
				const name = d[cdt_field("name")];

				return {
					name: name,
					doctype: col.docfield.parent,
					content: d[cdt_field(col.field)] || d[col.field],
					editable: Boolean(name && this.is_editable(col.docfield, d)),
					format: (value) => {
						return frappe.format(
							value,
							col.docfield,
							{ always_show_decimals: true },
							d
						);
					},
				};
			}
			if (col.field === "docstatus" && !frappe.meta.has_field(this.doctype, "status")) {
				// get status from docstatus
				let status = frappe.get_indicator(d, this.doctype);
				if (status) {
					// get_indicator returns the dependent field's condition as the 3rd parameter
					let dependent_col = status[2]?.split(",")[0];
					// add status dependency column
					this.add_status_dependency_column(dependent_col, this.doctype);
					return {
						name: d.name,
						doctype: col.docfield.parent,
						content: status[0],
						editable: false,
					};
				} else {
					// no status values found
					this.remove_column_from_datatable(col);
				}
			} else if (col.field in d) {
				const value = d[col.field];
				return {
					name: d.name,
					doctype: col.docfield.parent,
					content: value,
					editable: this.is_editable(col.docfield, d),
				};
			}
			return {
				content: "",
			};
		});
	}

	get_checked_items(only_docnames) {
		const indexes = this.datatable.rowmanager.getCheckedRows();
		const items = indexes.map((i) => this.data[i]).filter((i) => i != undefined);

		if (only_docnames) {
			return items.map((d) => d.name);
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
				page_length: this.page_length,
				column_widths: this.get_column_widths(),
				group_by: this.group_by_control.get_settings(),
				chart_args: this.get_chart_settings(),
			};

			return frappe.call({
				method: "frappe.desk.reportview.save_report",
				args: {
					name: name,
					doctype: this.doctype,
					report_settings: JSON.stringify(report_settings),
				},
				callback: (r) => {
					if (r.exc) {
						frappe.msgprint(__("Report was not saved (there were errors)"));
						return;
					}
					if (r.message != this.report_name) {
						// Rerender the reports dropdown,
						// so that this report is included in the dropdown as well.
						frappe.boot.user.all_reports[r.message] = {
							ref_doctype: this.doctype,
							report_type: "Report Builder",
							title: r.message,
						};

						frappe.set_route("List", this.doctype, "Report", r.message);
						return;
					}

					// update state
					this.report_doc.json = report_settings;
					this.set_dirty_state_for_custom_report();
				},
			});
		};

		if (this.report_name && save_type == "save") {
			_save_report(this.report_name);
		} else {
			frappe.prompt(
				{ fieldname: "name", label: __("New Report name"), reqd: 1, fieldtype: "Data" },
				(data) => {
					_save_report(data.name);
				},
				__("Save As")
			);
		}
	}

	delete_report() {
		return frappe.call({
			method: "frappe.desk.reportview.delete_report",
			args: { name: this.report_name },
			callback(response) {
				if (response.exc) return;
				window.history.back();
			},
		});
	}

	get_column_widths() {
		if (this.datatable) {
			return this.datatable.datamanager.getColumns(true).reduce((acc, curr) => {
				acc[curr.id] = parseInt(curr.width);
				return acc;
			}, {});
		}

		return {};
	}

	get_report_doc() {
		return new Promise((resolve) => {
			frappe.model.with_doc("Report", this.report_name, () => {
				resolve(frappe.get_doc("Report", this.report_name));
			});
		});
	}

	get_filters_html_for_print() {
		const filters = this.filter_area.get();

		return filters
			.map((f) => {
				const [doctype, fieldname, condition, value] = f;
				if (condition !== "=") return "";
				const label = frappe.meta.get_label(doctype, fieldname);
				const docfield = frappe.meta.get_docfield(doctype, fieldname);
				return `<h6>${__(label)}: ${frappe.format(value, docfield)}</h6>`;
			})
			.join("");
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
				label: __("Show Totals"),
				action: () => {
					this.add_totals_row = !this.add_totals_row;
					this.save_view_user_settings({
						add_totals_row: this.add_totals_row,
					});
					this.datatable.refresh(this.get_data(this.data));
				},
			},
			{
				label: __("Print"),
				action: () => {
					// prepare rows in their current state, sorted and filtered
					const rows_in_order = this.datatable.datamanager.rowViewOrder
						.map((index) => {
							if (this.datatable.bodyRenderer.visibleRowIndices.includes(index)) {
								return this.data[index];
							}
						})
						.filter(Boolean);

					if (this.add_totals_row) {
						const total_data = this.get_columns_totals(this.data);

						total_data["name"] = __("Totals").bold();
						rows_in_order.push(total_data);
					}

					frappe.ui.get_print_settings(false, (print_settings) => {
						var title = this.report_name || __(this.doctype);
						frappe.render_grid({
							title: title,
							subtitle: this.get_filters_html_for_print(),
							print_settings: print_settings,
							columns: this.columns,
							data: rows_in_order,
							can_use_smaller_font: 1,
						});
					});
				},
			},
			{
				label: __("Toggle Chart"),
				action: () => this.toggle_charts(),
			},
			{
				label: __("Toggle Sidebar"),
				action: () => this.toggle_side_bar(),
				shortcut: "Ctrl+K",
			},
			{
				label: __("Pick Columns"),
				action: () => {
					const d = new frappe.ui.Dialog({
						title: __("Pick Columns"),
						fields: this.get_dialog_fields(),
						primary_action: (values) => {
							// doctype fields
							let fields = values[this.doctype].map((f) => [f, this.doctype]);
							delete values[this.doctype];

							// child table fields
							for (let cdt in values) {
								fields = fields.concat(values[cdt].map((f) => [f, cdt]));
							}

							// always keep name (ID) column
							this.fields = [["name", this.doctype], ...fields];

							this.fields.map((f) => this.add_currency_column(f[0], f[1]));

							this.reorder_fields();
							this.build_fields();
							this.setup_columns();

							this.datatable.destroy();
							this.datatable = null;
							this.refresh();

							d.hide();
						},
					});

					d.$body.prepend(`
						<div class="columns-search">
							<input type="text" placeholder="${__(
								"Search"
							)}" data-element="search" class="form-control input-xs">
						</div>
					`);

					frappe.utils.setup_search(d.$body, ".unit-checkbox", ".label-area");
					d.show();
				},
			},
		];

		if (frappe.model.can_export(this.doctype)) {
			items.push({
				label: __("Export"),
				action: () => {
					const args = this.get_args();
					const selected_items = this.get_checked_items(true);
					let fields = [
						{
							fieldtype: "Select",
							label: __("Select File Type"),
							fieldname: "file_format_type",
							options: ["Excel", "CSV"],
							default: "Excel",
						},
					];

					if (this.total_count > this.count_without_children || args.page_length) {
						fields.push({
							fieldtype: "Check",
							fieldname: "export_all_rows",
							label: __("Export All {0} rows?", [(this.total_count + "").bold()]),
						});
					}

					const d = new frappe.ui.Dialog({
						title: __("Export Report: {0}", [__(this.doctype)]),
						fields: fields,
						primary_action_label: __("Download"),
						primary_action: (data) => {
							args.cmd = "frappe.desk.reportview.export_query";
							args.file_format_type = data.file_format_type;
							args.title = this.report_name || this.doctype;

							if (this.add_totals_row) {
								args.add_totals_row = 1;
							}

							if (selected_items.length > 0) {
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
				},
			});
		}

		items.push({
			label: __("Setup Auto Email"),
			action: () => {
				if (this.report_name) {
					frappe.set_route("List", "Auto Email Report", { report: this.report_name });
				} else {
					frappe.msgprint(__("Please save the report first"));
				}
			},
		});

		const can_edit_or_delete = (action) => {
			const method = action == "delete" ? "can_delete" : "can_write";
			return (
				this.report_doc &&
				this.report_doc.is_standard !== "Yes" &&
				(frappe.model[method]("Report") || this.report_doc.owner === frappe.session.user)
			);
		};

		// A user with role Report Manager or Report Owner can save
		if (can_edit_or_delete()) {
			items.push({
				label: __("Save"),
				action: () => this.save_report("save"),
			});
		}

		// anyone can save as
		items.push({
			label: __("Save As"),
			action: () => this.save_report("save_as"),
		});

		// A user with role Report Manager or Report Owner can delete
		if (can_edit_or_delete("delete")) {
			items.push({
				label: __("Delete"),
				action: () =>
					frappe.confirm("Are you sure you want to delete this report?", () =>
						this.delete_report()
					),
				shortcut: "Shift+Ctrl+D",
			});
		}

		// user permissions
		if (this.report_name && frappe.model.can_set_user_permissions("Report")) {
			items.push({
				label: __("User Permissions"),
				action: () => {
					const args = {
						doctype: "Report",
						name: this.report_name,
					};
					frappe.set_route("List", "User Permission", args);
				},
			});
		}

		if (frappe.user.has_role("System Manager")) {
			if (this.get_view_settings) {
				items.push(this.get_view_settings());
			}
		}

		return items.map((i) => Object.assign(i, { standard: true }));
	}
};
