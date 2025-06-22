import GridRowForm from "./grid_row_form";

export default class GridRow {
	constructor(opts) {
		this.on_grid_fields_dict = {};
		this.on_grid_fields = [];
		$.extend(this, opts);
		this.set_docfields();
		this.columns = {};
		this.columns_list = [];
		this.depandant_fields = {
			mandatory: [],
			read_only: [],
		};
		this.row_check_html = '<input type="checkbox" class="grid-row-check">';
		this.make();
	}
	make() {
		let me = this;
		let render_row = true;

		this.wrapper = $('<div class="grid-row"></div>');
		this.row = $('<div class="data-row row m-0"></div>')
			.appendTo(this.wrapper)
			.on("click", function (e) {
				if (
					$(e.target).hasClass("grid-row-check") ||
					$(e.target).hasClass("row-index") ||
					$(e.target).parent().hasClass("row-index")
				) {
					return;
				}
				if (me.grid.allow_on_grid_editing() && me.grid.is_editable()) {
					// pass
				} else {
					me.toggle_view();
					return false;
				}
			});

		if (this.grid.template && !this.grid.meta.editable_grid) {
			this.render_template();
		} else {
			render_row = this.render_row();
		}

		if (!render_row) return;

		this.set_data();
		this.wrapper.appendTo(this.parent);
	}

	set_docfields(update = false) {
		if (this.doc && this.parent_df.options) {
			frappe.meta.make_docfield_copy_for(
				this.parent_df.options,
				this.doc.name,
				this.docfields
			);
			const docfields = frappe.meta.get_docfields(this.parent_df.options, this.doc.name);
			if (update) {
				// to maintain references
				this.docfields.forEach((df) => {
					Object.assign(
						df,
						docfields.find((d) => d.fieldname === df.fieldname)
					);
				});
			} else {
				this.docfields = docfields;
			}
		}
	}

	set_data() {
		this.wrapper.data({
			grid_row: this,
			doc: this.doc || "",
		});
	}
	set_row_index() {
		if (this.doc) {
			this.wrapper
				.attr("data-name", this.doc.name)
				.attr("data-idx", this.doc.idx)
				.find(".row-index span, .grid-form-row-index")
				.html(this.doc.idx);
		}
	}
	select(checked) {
		this.doc.__checked = checked ? 1 : 0;
	}
	refresh_check() {
		this.wrapper
			.find(".grid-row-check")
			.prop("checked", this.doc ? !!this.doc.__checked : false);
		this.grid.debounced_refresh_remove_rows_button();
	}
	remove() {
		var me = this;
		if (this.grid.is_editable()) {
			if (this.get_open_form()) {
				this.hide_form();
			}
			if (this.frm) {
				frappe
					.run_serially([
						() => {
							return this.frm.script_manager.trigger(
								"before_" + this.grid.df.fieldname + "_remove",
								this.doc.doctype,
								this.doc.name
							);
						},
						() => {
							frappe.model.clear_doc(this.doc.doctype, this.doc.name);

							this.frm.script_manager.trigger(
								this.grid.df.fieldname + "_remove",
								this.doc.doctype,
								this.doc.name
							);
							this.frm.dirty();
							this.grid.refresh();
						},
					])
					.catch((e) => {
						// aborted
						console.trace(e);
					});
			} else {
				let data = null;
				if (this.grid.df.get_data) {
					data = this.grid.df.get_data();
				} else {
					data = this.grid.df.data;
				}

				const index = data.findIndex((d) => d.name === me.doc.name);

				if (index > -1) {
					// mutate array directly,
					// else the object reference will be lost
					data.splice(index, 1);
				}
				// remap idxs
				data.forEach(function (d, i) {
					d.idx = i + 1;
				});

				this.grid.refresh();
			}
		}
	}
	insert(show, below, duplicate) {
		var idx = this.doc.idx;
		var copy_doc = duplicate ? this.doc : null;
		if (below) idx++;
		this.toggle_view(false);
		this.grid.add_new_row(idx, null, show, copy_doc);
	}
	move() {
		// promopt the user where they want to move this row
		var me = this;
		frappe.prompt(
			{
				fieldname: "move_to",
				label: __("Move to Row Number"),
				fieldtype: "Int",
				reqd: 1,
				default: this.doc.idx,
			},
			function (values) {
				if (me.doc._sortable === false) {
					frappe.msgprint(__("Cannot move row"));
					return;
				}

				// renumber and refresh
				let data = me.grid.get_data();
				data.move(me.doc.idx - 1, values.move_to - 1);
				me.frm.dirty();

				// renum idx
				for (let i = 0; i < data.length; i++) {
					data[i].idx = i + 1;
				}

				me.toggle_view(false);
				me.grid.refresh();
				$(me.frm.wrapper).trigger("grid-move-row", [me.frm, me]);
			},
			__("Move To"),
			"Update"
		);
	}
	refresh() {
		// update docfields for new record
		if (this.frm && this.doc && this.doc.__islocal) {
			this.set_docfields(true);
		}

		if (this.frm && this.doc) {
			this.doc = locals[this.doc.doctype][this.doc.name];
		}

		if (this.grid.template && !this.grid.meta.editable_grid) {
			this.render_template();
		} else {
			this.render_row(true);
		}

		// refresh form fields
		if (this.grid_form) {
			this.grid_form.layout && this.grid_form.layout.refresh(this.doc);
		}
	}
	render_template() {
		this.set_row_index();

		if (this.row_display) {
			this.row_display.remove();
		}

		// row index
		if (!this.row_index) {
			this.row_index = $(
				`<div class="template-row-index">${this.row_check_html}<span></span></div>`
			).appendTo(this.row);
		}

		if (this.doc) {
			this.row_index.find("span").html(this.doc.idx);
		}

		this.row_display = $('<div class="row-data sortable-handle template-row"></div>')
			.appendTo(this.row)
			.html(
				frappe.render(this.grid.template, {
					doc: this.doc ? frappe.get_format_helper(this.doc) : null,
					frm: this.frm,
					row: this,
				})
			);
	}
	render_row(refresh) {
		if (this.show_search && !this.show_search_row()) return;

		let me = this;
		this.set_row_index();

		// index (1, 2, 3 etc)
		if (!this.row_index && !this.show_search) {
			const txt = this.doc
				? this.doc.idx
				: __("No.", null, "Title of the 'row number' column");

			this.row_check = $(
				`<div class="row-check sortable-handle col">
					${this.row_check_html}
				</div>`
			).appendTo(this.row);

			this.row_index = $(
				`<div class="row-index sortable-handle grid-static-col col">
					<span>${txt}</span>
				</div>`
			)
				.appendTo(this.row)
				.on("click", function (e) {
					if (!$(e.target).hasClass("grid-row-check")) {
						me.toggle_view();
					}
				});
		} else if (this.show_search) {
			this.row_check = $(`
				<div class="row-check col search">
					<input type="text" class="form-control input-xs text-center invisible">
				</div>`).appendTo(this.row);

			this.row_index = $(
				`<div class="row-index col search">
					<input type="text" class="form-control input-xs text-center" >
					<span style="width: 33px;" class="d-block"></span>
				</div>`
			).appendTo(this.row);

			this.row_index.find("input").on(
				"keyup",
				frappe.utils.debounce((e) => {
					let df = {
						fieldtype: "Sr No",
					};

					this.grid.filter["row-index"] = {
						df: df,
						value: e.target.value,
					};

					if (e.target.value == "") {
						delete this.grid.filter["row-index"];
					}

					this.grid.grid_sortable.option(
						"disabled",
						Object.keys(this.grid.filter).length !== 0
					);

					this.grid.prevent_build = true;
					me.grid.refresh();
					this.grid.prevent_build = false;
				}, 500)
			);
			frappe.utils.only_allow_num_decimal(this.row_index.find("input"));
		}

		this.setup_columns();
		this.add_open_form_button();
		this.add_column_configure_button();
		this.refresh_check();

		if (this.frm && this.doc) {
			$(this.frm.wrapper).trigger("grid-row-render", [this]);
		}

		return true;
	}

	make_editable() {
		this.row.toggleClass("editable-row", this.grid.is_editable());
	}

	is_too_small() {
		return this.row.width() ? this.row.width() < 300 : false;
	}

	add_open_form_button() {
		var me = this;
		if (this.doc && !this.grid.df.in_place_edit) {
			// remove row
			if (!this.open_form_button) {
				this.open_form_button = $('<div class="col"></div>').appendTo(this.row);

				if (!this.configure_columns) {
					const edit_msg = __("Edit", "", "Edit grid row");
					this.open_form_button = $(`
						<div class="btn-open-row" data-toggle="tooltip" data-placement="right" title="${edit_msg}">
							<a>${frappe.utils.icon("edit", "xs")}</a>
						</div>
					`)
						.appendTo(this.open_form_button)
						.on("click", function () {
							me.toggle_view();
							return false;
						});

					this.open_form_button.tooltip({ delay: { show: 600, hide: 100 } });
				}

				if (this.is_too_small()) {
					// narrow
					this.open_form_button.css({ "margin-right": "-2px" });
				}
			}
		}
	}

	add_column_configure_button() {
		if (this.grid.df.in_place_edit && !this.frm) return;

		if (this.configure_columns && this.frm) {
			this.configure_columns_button = $(`
				<div class="col grid-static-col pointer">
					<a>${frappe.utils.icon("setting-gear", "sm", "", "filter: opacity(0.5)")}</a>
				</div>
			`)
				.appendTo(this.row)
				.on("click", () => {
					this.configure_dialog_for_columns_selector();
				});
		} else if (this.configure_columns && !this.frm) {
			this.configure_columns_button = $(`
				<div class="col grid-static-col"></div>
			`).appendTo(this.row);
		}
	}

	configure_dialog_for_columns_selector() {
		this.grid_settings_dialog = new frappe.ui.Dialog({
			title: __("Configure Columns"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "fields_html",
				},
			],
		});

		this.grid.setup_visible_columns();
		this.setup_columns_for_dialog();
		this.prepare_wrapper_for_columns();
		this.render_selected_columns();
		this.grid_settings_dialog.show();

		$(this.fields_html_wrapper)
			.find(".add-new-fields")
			.click(() => {
				this.column_selector_for_dialog();
			});

		this.grid_settings_dialog.set_primary_action(__("Update"), () => {
			this.columns = {};
			this.update_user_settings_for_grid();
			this.grid_settings_dialog.hide();
		});

		this.grid_settings_dialog.set_secondary_action_label(__("Reset to default"));
		this.grid_settings_dialog.set_secondary_action(() => {
			this.reset_user_settings_for_grid();
			this.grid_settings_dialog.hide();
		});
	}

	setup_columns_for_dialog() {
		this.selected_columns_for_grid = [];
		this.grid.visible_columns.forEach((row) => {
			this.selected_columns_for_grid.push({
				fieldname: row[0].fieldname,
				columns: row[0].columns || row[0].colsize,
				sticky: row[0].sticky,
			});
		});
	}

	prepare_wrapper_for_columns() {
		this.fields_html_wrapper = this.grid_settings_dialog.get_field("fields_html").$wrapper[0];

		$(`
			<div class='form-group'>
				<div class='row' style='margin-bottom:10px;'>
					<div class='col-1'></div>
					<div class='col-5' style='padding-left:20px;'>
						${__("Fieldname").bold()}
					</div>
					<div class='col-3'>
						${__("Column Width").bold()}
					</div>
					<div class='col-2'>
						${__("Sticky").bold()}
					</div>
					<div class='col-1'></div>
				</div>
				<div class='control-input-wrapper selected-fields'>
				</div>
				<p class='help-box small text-muted'>
					<a class='add-new-fields text-muted'>
						+ ${__("Add / Remove Columns")}
					</a>
				</p>
			</div>
		`).appendTo(this.fields_html_wrapper);
	}

	column_selector_for_dialog() {
		let docfields = this.prepare_columns_for_dialog(
			this.selected_columns_for_grid.map((field) => field.fieldname)
		);

		let d = new frappe.ui.Dialog({
			title: __("{0} Fields", [__(this.grid.doctype)]),
			fields: [
				{
					label: __("Select Fields"),
					fieldtype: "MultiCheck",
					fieldname: "fields",
					options: docfields,
					columns: 2,
					sort_options: false,
				},
			],
			secondary_action_label: __("Select All"),
			secondary_action: () => this.select_all_columns(docfields),
		});

		d.set_primary_action(__("Add"), () => {
			let selected_fields = d.get_values().fields;
			this.selected_columns_for_grid = [];
			if (selected_fields) {
				selected_fields.forEach((selected_column) => {
					let docfield = frappe.meta.get_docfield(this.grid.doctype, selected_column);
					this.grid.update_default_colsize(docfield);

					this.selected_columns_for_grid.push({
						fieldname: selected_column,
						columns: docfield.columns || docfield.colsize,
					});
				});

				this.render_selected_columns();
				d.hide();
			}
		});

		d.show();
	}

	select_all_columns(docfields) {
		docfields.forEach((docfield) => {
			if (docfield.checked) {
				return;
			}
			$(`.checkbox.unit-checkbox input[type="checkbox"][data-unit="${docfield.value}"]`)
				.prop("checked", true)
				.trigger("change");
		});
	}

	prepare_columns_for_dialog(selected_fields) {
		let fields = [];

		const blocked_fields = frappe.model.no_value_type;
		const always_allow = ["Button"];

		const show_field = (f) => always_allow.includes(f) || !blocked_fields.includes(f);

		// First, add selected fields
		selected_fields.forEach((selectedField) => {
			const selectedColumn = this.docfields.find(
				(column) => column.fieldname === selectedField
			);
			if (selectedColumn && !selectedColumn.hidden && show_field(selectedColumn.fieldtype)) {
				fields.push({
					label: __(selectedColumn.label, null, this.grid.doctype),
					value: selectedColumn.fieldname,
					checked: true,
				});
			}
		});

		// Then, add the rest of the fields
		this.docfields.forEach((column) => {
			if (
				!selected_fields.includes(column.fieldname) &&
				!column.hidden &&
				show_field(column.fieldtype)
			) {
				fields.push({
					label: __(column.label, null, this.grid.doctype),
					value: column.fieldname,
					checked: false,
				});
			}
		});

		return fields;
	}

	render_selected_columns() {
		let fields = "";
		if (this.selected_columns_for_grid) {
			this.selected_columns_for_grid.forEach((d) => {
				let docfield = frappe.meta.get_docfield(this.grid.doctype, d.fieldname);

				fields += `
					<div class='control-input flex align-center form-control fields_order sortable-handle sortable'
						style='display: block; margin-bottom: 5px; padding: 0 8px; cursor: pointer; height: 32px;' data-fieldname='${
							docfield.fieldname
						}'
						data-label='${docfield.label}' data-type='${docfield.fieldtype}'>

						<div class='row'>
							<div class='col-1' style='padding-top: 4px;'>
								<a style='cursor: grabbing;'>${frappe.utils.icon("drag", "xs")}</a>
							</div>
							<div class='col-5' style='padding-top: 5px;'>
								${__(docfield.label, null, docfield.parent)}
							</div>
							<div class='col-3' style='padding-top: 2px; margin-top:-2px;' title='${__("Columns")}'>
								<input class='form-control column-width my-1 input-xs text-right'
								style='height: 24px; max-width: 80px; background: var(--bg-color);'
									value='${docfield.columns || cint(d.columns)}'
									data-fieldname='${docfield.fieldname}' style='background-color: var(--modal-bg); display: inline'>
							</div>
							<div class='col-2' title='${__("Sticky")}'>
								<input type='checkbox' class='form-control sticky-column'
									style='margin-top: 8px'
									${docfield.sticky ? "checked" : ""}
									data-fieldname='${docfield.fieldname}' style='background-color: var(--modal-bg); display: inline'>
							</div>
							<div class='col-1' style='padding-top: 3px;'>
								<a class='text-muted remove-field' data-fieldname='${docfield.fieldname}'>
									<i class='fa fa-trash-o' aria-hidden='true'></i>
								</a>
							</div>
						</div>
					</div>`;
			});
		}

		$(this.fields_html_wrapper).find(".selected-fields").html(fields);

		this.prepare_handler_for_sort();
		this.select_on_focus();
		this.update_column_width();
		this.update_sticky_column();
		this.remove_selected_column();
	}

	prepare_handler_for_sort() {
		new Sortable($(this.fields_html_wrapper).find(".selected-fields")[0], {
			handle: ".sortable-handle",
			draggable: ".sortable",
			onUpdate: () => {
				this.sort_columns();
			},
		});
	}

	sort_columns() {
		this.selected_columns_for_grid = [];

		let columns = $(this.fields_html_wrapper).find(".fields_order") || [];
		columns.each((idx) => {
			this.selected_columns_for_grid.push({
				fieldname: $(columns[idx]).attr("data-fieldname"),
				columns: cint($(columns[idx]).find(".column-width").attr("value")),
			});
		});
	}

	select_on_focus() {
		$(this.fields_html_wrapper)
			.find(".column-width")
			.click((event) => {
				$(event.target).select();
			});
	}

	update_column_width() {
		$(this.fields_html_wrapper)
			.find(".column-width")
			.change((event) => {
				if (cint(event.target.value) === 0) {
					event.target.value = cint(event.target.defaultValue);
					frappe.throw(__("Column width cannot be zero."));
				}

				this.selected_columns_for_grid.forEach((row) => {
					if (row.fieldname === event.target.dataset.fieldname) {
						row.columns = cint(event.target.value);
						event.target.defaultValue = cint(event.target.value);
					}
				});
			});
	}

	update_sticky_column() {
		$(this.fields_html_wrapper)
			.find(".sticky-column")
			.change((event) => {
				this.selected_columns_for_grid.forEach((row) => {
					if (row.fieldname === event.target.dataset.fieldname) {
						row.sticky = cint(event.target.checked);
						event.target.defaultValue = cint(event.target.checked);
					}
				});
			});
	}

	remove_selected_column() {
		$(this.fields_html_wrapper)
			.find(".remove-field")
			.click((event) => {
				let fieldname = event.currentTarget.dataset.fieldname;
				let selected_columns_for_grid = this.selected_columns_for_grid.filter((row) => {
					return row.fieldname !== fieldname;
				});

				if (selected_columns_for_grid && selected_columns_for_grid.length === 0) {
					frappe.throw(__("At least one column is required to show in the grid."));
				}

				this.selected_columns_for_grid = selected_columns_for_grid;
				$(this.fields_html_wrapper).find(`[data-fieldname="${fieldname}"]`).remove();
			});
	}

	update_user_settings_for_grid() {
		if (!this.selected_columns_for_grid || !this.frm) {
			return;
		}

		let value = {};
		value[this.grid.doctype] = this.selected_columns_for_grid;
		frappe.model.user_settings.save(this.frm.doctype, "GridView", value).then((r) => {
			frappe.model.user_settings[this.frm.doctype] = r.message || r;
			this.grid.reset_grid();
		});
	}

	reset_user_settings_for_grid() {
		frappe.model.user_settings.save(this.frm.doctype, "GridView", null).then((r) => {
			frappe.model.user_settings[this.frm.doctype] = r.message || r;
			this.grid.reset_grid();
		});
	}

	setup_columns() {
		this.focus_set = false;
		this.search_columns = {};

		this.grid.setup_visible_columns();
		let fields =
			this.grid.user_defined_columns && this.grid.user_defined_columns.length > 0
				? this.grid.user_defined_columns
				: this.docfields;

		let total_colsize = 0;

		this.grid.visible_columns.forEach((col, ci) => {
			// to get update df for the row
			let df = fields.find((field) => field?.fieldname === col[0].fieldname);

			this.set_dependant_property(df);

			let colsize = col[1];

			total_colsize += colsize;
			let txt = this.doc
				? frappe.format(this.doc[df.fieldname], df, null, this.doc)
				: __(df.label, null, df.parent);

			if (this.doc && df.fieldtype === "Select") {
				txt = __(txt);
			}
			let column;
			if (!this.columns[df.fieldname] && !this.show_search) {
				column = this.make_column(df, colsize, txt, ci);
			} else if (!this.columns[df.fieldname] && this.show_search) {
				column = this.make_search_column(df, colsize);
			} else {
				column = this.columns[df.fieldname];
				this.refresh_field(df.fieldname, txt);
			}

			// background color for cell
			if (this.doc) {
				if (df.reqd && !txt) {
					column.addClass("error");
				}
				if (column.is_invalid) {
					column.addClass("invalid");
				} else if (df.reqd || df.bold) {
					column.addClass("bold");
				}
			}
		});

		let current_grid = $(
			`div[data-fieldname="${this.grid.df.fieldname}"] .form-grid-container`
		);
		if (total_colsize > 10) {
			current_grid.addClass("column-limit-reached");
		} else if (current_grid.hasClass("column-limit-reached")) {
			if (Number($(current_grid).children(".form-grid").css("left")) != 0) {
				$(current_grid).children(".form-grid").css("left", 0);
				$(current_grid).children().find(".grid-scroll-bar").css({
					width: "auto",
					"margin-left": "0px",
				});
				$(current_grid).children().find(".grid-scroll-bar-rows").css("width", "auto");
			}
			current_grid.removeClass("column-limit-reached");
		}

		if (this.show_search) {
			// last empty column
			$(`<div class="col grid-static-col search"></div>`).appendTo(this.row);
		}
	}

	set_dependant_property(df) {
		if (
			!df.reqd &&
			df.mandatory_depends_on &&
			this.evaluate_depends_on_value(df.mandatory_depends_on)
		) {
			df.reqd = 1;
			this.depandant_fields["mandatory"].push(df);
		}

		if (
			!df.read_only &&
			df.read_only_depends_on &&
			this.evaluate_depends_on_value(df.read_only_depends_on)
		) {
			df.read_only = 1;
			this.depandant_fields["read_only"].push(df);
		}
	}

	refresh_depedency() {
		this.depandant_fields["read_only"].forEach((df) => {
			df.read_only = 0;
			this.set_dependant_property(df);
		});
		this.depandant_fields["mandatory"].forEach((df) => {
			df.reqd = 0;
			this.set_dependant_property(df);
		});
		this.refresh();
	}

	evaluate_depends_on_value(expression) {
		let out = null;
		let doc = this.doc;

		if (!doc) return;

		let parent = this.frm ? this.frm.doc : this.doc || null;

		if (typeof expression === "boolean") {
			out = expression;
		} else if (typeof expression === "function") {
			out = expression(doc);
		} else if (expression.substr(0, 5) == "eval:") {
			try {
				out = frappe.utils.eval(expression.substr(5), { doc, parent });
				if (parent && parent.istable && expression.includes("is_submittable")) {
					out = true;
				}
			} catch (e) {
				frappe.throw(__('Invalid "depends_on" expression'));
			}
		} else if (expression.substr(0, 3) == "fn:" && this.frm) {
			out = this.frm.script_manager.trigger(
				expression.substr(3),
				this.doctype,
				this.docname
			);
		} else {
			var value = doc[expression];
			if ($.isArray(value)) {
				out = !!value.length;
			} else {
				out = !!value;
			}
		}

		return out;
	}

	show_search_row() {
		// show or remove search columns based on grid rows
		let show_length =
			this.grid?.meta?.rows_threshold_for_grid_search > 0
				? this.grid.meta.rows_threshold_for_grid_search
				: 20;
		this.show_search =
			this.show_search &&
			(this.grid?.data?.length >= show_length || this.grid.filter_applied);
		!this.show_search && this.wrapper.remove();
		return this.show_search;
	}

	make_search_column(df, colsize) {
		let title = "";
		let input_class = "";
		let is_disabled = "";

		if (["Text", "Small Text"].includes(df.fieldtype)) {
			input_class = "grid-overflow-no-ellipsis";
		} else if (["Int", "Currency", "Float", "Percent"].includes(df.fieldtype)) {
			input_class = "text-right";
		} else if (df.fieldtype === "Check") {
			title = __("1 = True & 0 = False");
			input_class = "text-center";
		} else if (df.fieldtype === "Password") {
			is_disabled = "disabled";
			title = __("Password cannot be filtered");
		}

		let $col = $(
			'<div class="col grid-static-col col-xs-' + colsize + ' search"></div>'
		).appendTo(this.row);

		let $search_input = $(`
			<input
				type="text"
				class="form-control input-xs ${input_class}"
				title="${title}"
				data-fieldtype="${df.fieldtype}"
				${is_disabled}
			>
		`).appendTo($col);

		this.search_columns[df.fieldname] = $col;

		$search_input.on(
			"keyup",
			frappe.utils.debounce((e) => {
				this.grid.filter[df.fieldname] = {
					df: df,
					value: e.target.value,
				};

				if (e.target.value == "") {
					delete this.grid.filter[df.fieldname];
				}

				if (this.grid.grid_sortable) {
					this.grid.grid_sortable.option(
						"disabled",
						Object.keys(this.grid.filter).length !== 0
					);
				}

				this.grid.prevent_build = true;
				this.grid.grid_pagination.go_to_page(1);
				this.grid.refresh();
				this.grid.prevent_build = false;
			}, 500)
		);

		["Currency", "Float", "Int", "Percent", "Rating"].includes(df.fieldtype) &&
			frappe.utils.only_allow_num_decimal($search_input);

		return $col;
	}

	make_column(df, colsize, txt, ci) {
		let col_sizes = {
			1: 60,
			2: 100,
			3: 140,
			4: 200,
			5: 250,
			6: 300,
			7: 350,
			8: 400,
			9: 450,
			10: 500,
			11: 550,
			12: 600,
		};
		let me = this;
		var add_class =
			["Text", "Small Text"].indexOf(df.fieldtype) !== -1
				? " grid-overflow-no-ellipsis"
				: "";
		add_class +=
			["Int", "Currency", "Float", "Percent"].indexOf(df.fieldtype) !== -1
				? " text-right"
				: "";
		add_class += ["Check"].indexOf(df.fieldtype) !== -1 ? " text-center" : "";

		let add_style = "";
		if (df.sticky) {
			add_class += " sticky-grid-col";
			if (!(df.fieldname in this.grid.sticky_rows)) {
				this.grid.sticky_rows[df.fieldname] = this.grid.sticky_row_sum;
				this.grid.sticky_row_sum = Object.keys(this.grid.sticky_rows).length
					? this.grid.sticky_row_sum + col_sizes[colsize]
					: this.grid.sticky_row_sum;
			}
			add_style += `left: ${this.grid.sticky_rows[df.fieldname] || 71}px;`;
		}

		let grid;
		let grid_container;
		let input_in_focus = false;

		// prevent random layout shifts caused by widgets and on click position elements inside view (UX).
		function on_input_focus(el) {
			input_in_focus = true;

			let container_width = grid_container.getBoundingClientRect().width;
			let container_left = grid_container.getBoundingClientRect().left;
			let grid_left = parseFloat(grid.style.left);
			let element_left = el.offset().left;
			let fieldtype = el.data("fieldtype");

			let offset_right = container_width - (element_left + el.width());
			let offset_left = 0;
			let element_screen_x = element_left - container_left;
			let element_position_x = container_width - (element_left - container_left);

			if (["Date", "Time", "Datetime"].includes(fieldtype)) {
				offset_left = element_position_x - 220;
			}
			if (["Link", "Dynamic Link"].includes(fieldtype)) {
				offset_left = element_position_x - 250;
			}
			if (element_screen_x < 0) {
				grid.style.left = `${grid_left - element_screen_x}px`;
			} else if (offset_left < 0) {
				grid.style.left = `${grid_left + offset_left}px`;
			} else if (offset_right < 0) {
				grid.style.left = `${grid_left + offset_right}px`;
			}
		}

		// Delay date_picker widget to prevent temparary layout shift (UX).
		function handle_date_picker() {
			let date_time_picker = document.querySelectorAll(".datepicker.active")[0];

			date_time_picker.classList.remove("active");
			date_time_picker.style.width = "220px";

			setTimeout(() => {
				date_time_picker.classList.add("active");
			}, 600);
		}

		function trigger_focus(input_field, col_df) {
			if (["Date", "Datetime"].includes(col_df.fieldtype) && col_df?.read_only) {
				return;
			}

			input_field.trigger("focus");
		}

		var $col = $(
			`<div class="col grid-static-col col-xs-${colsize} ${add_class}" style="${add_style}"></div>`
		)
			.attr("data-fieldname", df.fieldname)
			.attr("data-fieldtype", df.fieldtype)
			.data("df", df)
			.appendTo(this.row)
			.on("click", function (event) {
				if (df.fieldtype === "Link" || df.fieldtype === "Dynamic Link") {
					frappe.utils.sleep(500).then(() => {
						let element_position = event.target.getBoundingClientRect();
						$(this)
							.find(".awesomplete > ul:first-of-type")
							.css(
								"top",
								`${
									element_position.bottom
										? element_position.bottom
										: event.clientY + 20
								}px`
							);
					});
				}
				if (frappe.ui.form.editable_row !== me) {
					var out = me.toggle_editable_row();
				}
				var col = this;
				let first_input_field = $(col).find('input[type="Text"]:first');
				let input_in_focus = false;

				$(col)
					.find("input[type='text']")
					.each(function () {
						if ($(this).is(":focus")) {
							input_in_focus = true;
						}
					});

				!input_in_focus && trigger_focus(first_input_field, $(col).data("df"));

				if (event.pointerType == "touch") {
					first_input_field.length && on_input_focus(first_input_field);

					first_input_field.one("blur", () => (input_in_focus = false));

					first_input_field.data("fieldtype") == "Date" && handle_date_picker();
				}

				return out;
			});

		$col.field_area = $('<div class="field-area"></div>').appendTo($col).toggle(false);
		$col.static_area = $('<div class="static-area ellipsis"></div>').appendTo($col).html(txt);

		// set title attribute to see full label for columns in the heading row
		if (!this.doc) {
			$col.attr("title", txt);
		}
		df.fieldname && $col.static_area.toggleClass("reqd", Boolean(df.reqd));

		$col.df = df;
		$col.column_index = ci;

		this.columns[df.fieldname] = $col;
		this.columns_list.push($col);

		return $col;
	}

	activate() {
		this.toggle_editable_row(true);
		return this;
	}

	toggle_editable_row(show) {
		var me = this;
		// show static for field based on
		// whether grid is editable
		if (
			this.grid.allow_on_grid_editing() &&
			this.grid.is_editable() &&
			this.doc &&
			show !== false
		) {
			// disable other editable row
			if (frappe.ui.form.editable_row && frappe.ui.form.editable_row !== this) {
				frappe.ui.form.editable_row.toggle_editable_row(false);
			}

			this.row.toggleClass("editable-row", true);

			// setup controls
			this.columns_list.forEach(function (column) {
				me.make_control(column);
				column.static_area.toggle(false);
				column.field_area.toggle(true);
			});

			frappe.ui.form.editable_row = this;
			return false;
		} else {
			this.row.toggleClass("editable-row", false);

			this.columns_list.forEach((column, index) => {
				if (!this.frm) {
					let df = this.grid.visible_columns[index][0];

					let txt = this.doc
						? frappe.format(this.doc[df.fieldname], df, null, this.doc)
						: __(df.label, null, df.parent);

					this.refresh_field(df.fieldname, txt);
				}

				if (!column.df.hidden) {
					column.static_area.toggle(true);
				}

				column.field_area && column.field_area.toggle(false);
			});
			frappe.ui.form.editable_row = null;
		}
	}

	make_control(column) {
		if (column.field) return;

		var me = this,
			parent = column.field_area,
			df = column.df;
		var field = frappe.ui.form.make_control({
			df: df,
			parent: parent,
			only_input: true,
			with_link_btn: true,
			doc: this.doc,
			doctype: this.doc.doctype,
			docname: this.doc.name,
			frm: this.grid.frm,
			grid: this.grid,
			grid_row: this,
			value: this.doc[df.fieldname],
		});

		// sync get_query
		field.get_query = this.grid.get_field(df.fieldname).get_query;
		// df.onchange is common for all rows in grid
		let field_on_change_function = df.onchange;
		field.df.change = (e) => {
			this.refresh_depedency();
			// trigger onchange with current grid row field as "this"
			field_on_change_function && field_on_change_function.apply(field, [e]);
			me.refresh_field(field.df.fieldname);
		};

		field.refresh();
		if (field.$input) {
			field.$input
				.addClass("input-sm")
				.attr("data-col-idx", column.column_index)
				.attr("placeholder", __(df.placeholder || df.label));
			// flag list input
			if (this.columns_list && this.columns_list.slice(-1)[0] === column) {
				field.$input.attr("data-last-input", 1);
			}
		}

		this.set_arrow_keys(field);
		column.field = field;
		this.on_grid_fields_dict[df.fieldname] = field;
		this.on_grid_fields.push(field);
	}

	set_arrow_keys(field) {
		var me = this;
		let ignore_fieldtypes = ["Text", "Small Text", "Code", "Text Editor", "HTML Editor"];
		if (field.$input) {
			field.$input.on("keydown", function (e) {
				var { ESCAPE, TAB, UP: UP_ARROW, DOWN: DOWN_ARROW } = frappe.ui.keyCode;
				if (![TAB, UP_ARROW, DOWN_ARROW, ESCAPE].includes(e.which)) {
					return;
				}

				var values = me.grid.get_data();
				var fieldname = $(this).attr("data-fieldname");
				var fieldtype = $(this).attr("data-fieldtype");

				let ctrl_key = e.metaKey || e.ctrlKey;
				if (!ignore_fieldtypes.includes(fieldtype) && ctrl_key && e.which !== TAB) {
					me.add_new_row_using_keys(e);
					return;
				}

				if (e.shiftKey && e.altKey && DOWN_ARROW === e.which) {
					me.duplicate_row_using_keys();
					return;
				}

				var move_up_down = function (base) {
					if (ignore_fieldtypes.includes(fieldtype) && !e.altKey) {
						return false;
					}
					if (field.autocomplete_open) {
						return false;
					}

					base.toggle_editable_row();
					var input = base.columns[fieldname].field.$input;
					if (input) {
						input.focus();
					}
					return true;
				};

				// ESC
				if (e.which === ESCAPE && !e.shiftKey) {
					if (me.doc.__unedited) {
						me.grid.grid_rows[me.doc.idx - 1].remove();
					}
					return false;
				}

				// TAB
				if (e.which === TAB && !e.shiftKey) {
					var last_column = me.wrapper.find(":input:enabled:last").get(0);
					var is_last_column = $(this).attr("data-last-input") || last_column === this;

					if (is_last_column) {
						// last row
						if (me.doc.idx === values.length) {
							setTimeout(function () {
								me.grid.add_new_row(null, null, true);
								me.grid.grid_rows[
									me.grid.grid_rows.length - 1
								].toggle_editable_row();
								me.grid.set_focus_on_row();
							}, 100);
						} else {
							// last column before last row
							me.grid.grid_rows[me.doc.idx].toggle_editable_row();
							me.grid.set_focus_on_row(me.doc.idx);
							return false;
						}
					}
				} else if (e.which === UP_ARROW) {
					if (me.doc.idx > 1) {
						var prev = me.grid.grid_rows[me.doc.idx - 2];
						if (move_up_down(prev)) {
							return false;
						}
					}
				} else if (e.which === DOWN_ARROW) {
					if (me.doc.idx < values.length) {
						var next = me.grid.grid_rows[me.doc.idx];
						if (move_up_down(next)) {
							return false;
						}
					}
				}
			});
		}
	}

	duplicate_row_using_keys() {
		setTimeout(() => {
			this.insert(false, true, true);
			this.grid.grid_rows[this.doc.idx].toggle_editable_row();
			this.grid.set_focus_on_row(this.doc.idx);
		}, 100);
	}

	add_new_row_using_keys(e) {
		let idx = "";

		let ctrl_key = e.metaKey || e.ctrlKey;
		let is_down_arrow_key_press = e.which === 40;

		// Add new row at the end or start of the table
		if (ctrl_key && e.shiftKey) {
			idx = is_down_arrow_key_press ? null : 1;
			this.grid.add_new_row(
				idx,
				null,
				is_down_arrow_key_press,
				false,
				is_down_arrow_key_press,
				!is_down_arrow_key_press
			);
			idx = is_down_arrow_key_press ? cint(this.grid.grid_rows.length) - 1 : 0;
		} else if (ctrl_key) {
			idx = is_down_arrow_key_press ? this.doc.idx : this.doc.idx - 1;
			this.insert(false, is_down_arrow_key_press);
		}

		if (idx !== "") {
			setTimeout(() => {
				this.grid.grid_rows[idx].toggle_editable_row();
				this.grid.set_focus_on_row(idx);
			}, 100);
		}
	}

	get_open_form() {
		return frappe.ui.form.get_open_grid_form();
	}

	toggle_view(show, callback) {
		if (!this.doc) {
			return this;
		}

		if (this.frm) {
			// reload doc
			this.doc = locals[this.doc.doctype][this.doc.name];
		}

		// hide other
		var open_row = this.get_open_form();

		if (show === undefined) show = !open_row;

		// call blur
		document.activeElement && document.activeElement.blur();

		if (show && open_row) {
			if (open_row == this) {
				// already open, do nothing
				callback && callback();
				return;
			} else {
				// close other views
				open_row.toggle_view(false);
			}
		}

		if (show) {
			this.show_form();
		} else {
			this.hide_form();
		}
		callback && callback();

		return this;
	}
	show_form() {
		if (frappe.utils.is_xs()) {
			$(this.grid.form_grid).css("min-width", "0");
			$(this.grid.form_grid).css("position", "unset");
		}
		if (!this.grid_form) {
			this.grid_form = new GridRowForm({
				row: this,
			});
		}
		this.grid_form.render();
		this.row.toggle(false);
		// this.form_panel.toggle(true);

		let cannot_add_rows =
			this.grid.cannot_add_rows || (this.grid.df && this.grid.df.cannot_add_rows);
		this.wrapper
			.find(
				".grid-insert-row-below, .grid-insert-row, .grid-duplicate-row, .grid-append-row"
			)
			.toggle(!cannot_add_rows);

		this.wrapper
			.find(".grid-delete-row")
			.toggle(!(this.grid.df && this.grid.df.cannot_delete_rows));

		frappe.dom.freeze("", "dark grid-form");
		if (cur_frm) cur_frm.cur_grid = this;
		this.wrapper.addClass("grid-row-open");
		if (
			!frappe.dom.is_element_in_viewport(this.wrapper) &&
			!frappe.dom.is_element_in_modal(this.wrapper)
		) {
			// -15 offset to make form look visually centered
			frappe.utils.scroll_to(this.wrapper, true, -15);
		}

		if (this.frm) {
			this.frm.script_manager.trigger(this.doc.parentfield + "_on_form_rendered");
			this.frm.script_manager.trigger("form_render", this.doc.doctype, this.doc.name);
		}
	}
	hide_form() {
		if (frappe.utils.is_xs()) {
			$(this.grid.form_grid).css("min-width", "738px");
			$(this.grid.form_grid).css("position", "relative");
		}
		frappe.dom.unfreeze();
		this.row.toggle(true);
		if (!frappe.dom.is_element_in_modal(this.row)) {
			frappe.utils.scroll_to(this.row, true, 15);
		}
		this.refresh();
		if (cur_frm) cur_frm.cur_grid = null;
		this.wrapper.removeClass("grid-row-open");
	}
	has_prev() {
		return this.doc.idx > 1;
	}
	open_prev() {
		if (!this.doc) return;
		this.open_row_at_index(this.doc.idx - 2);
	}
	has_next() {
		return this.doc.idx < this.grid.data.length;
	}
	open_next() {
		if (!this.doc) return;

		this.open_row_at_index(this.doc.idx);
	}
	open_row_at_index(row_index) {
		if (!this.grid.data[row_index]) return;

		this.change_page_if_reqd(row_index);
		this.grid.grid_rows[row_index].toggle_view(true);
		return true;
	}
	change_page_if_reqd(row_index) {
		const { page_index, page_length } = this.grid.grid_pagination;

		row_index++;
		let new_page;

		if (row_index <= (page_index - 1) * page_length) {
			new_page = page_index - 1;
		} else if (row_index > page_index * page_length) {
			new_page = page_index + 1;
		}

		if (new_page) {
			this.grid.grid_pagination.go_to_page(new_page);
		}
	}
	refresh_field(fieldname, txt) {
		let fields =
			this.grid.user_defined_columns && this.grid.user_defined_columns.length > 0
				? this.grid.user_defined_columns
				: this.docfields;

		let df = fields.find((col) => {
			return col?.fieldname === fieldname;
		});

		// format values if no frm
		if (df && this.doc) {
			txt = frappe.format(this.doc[fieldname], df, null, this.doc);
		}

		if (!txt && this.frm) {
			txt = frappe.format(this.doc[fieldname], df, null, this.frm.doc);
		}

		// reset static value
		let column = this.columns[fieldname];
		if (column) {
			column.static_area.html(txt || "");
			if (df && df.reqd) {
				column.toggleClass("error", !!(txt === null || txt === ""));
			}
		}

		let field = this.on_grid_fields_dict[fieldname];
		// reset field value
		if (field) {
			// the below if statement is added to factor in the exception when this.doc is undefined -
			// - after row removals via customize_form.js on links, actions and states child-tables
			if (this.doc) field.docname = this.doc.name;
			field.refresh();
		}

		// in form
		if (this.grid_form) {
			this.grid_form.refresh_field(fieldname);
		}
	}
	get_field(fieldname) {
		let field = this.on_grid_fields_dict[fieldname];
		if (field) {
			return field;
		} else if (this.grid_form) {
			return this.grid_form.fields_dict[fieldname];
		} else {
			throw `fieldname ${fieldname} not found`;
		}
	}

	get_visible_columns(blacklist = []) {
		var me = this;
		var visible_columns = $.map(this.docfields, function (df) {
			var visible =
				!df.hidden &&
				df.in_list_view &&
				me.grid.frm.get_perm(df.permlevel, "read") &&
				!frappe.model.layout_fields.includes(df.fieldtype) &&
				!blacklist.includes(df.fieldname);

			return visible ? df : null;
		});
		return visible_columns;
	}
	set_field_property(fieldname, property, value) {
		// set a field property for open form / grid form
		var me = this;

		var set_property = function (field) {
			if (!field) return;
			field.df[property] = value;
			field.refresh();
		};

		// set property in grid form
		if (this.grid_form) {
			set_property(this.grid_form.fields_dict[fieldname]);
			this.grid_form.layout && this.grid_form.layout.refresh_sections();
		}

		// set property in on grid fields
		set_property(this.on_grid_fields_dict[fieldname]);
	}
	toggle_reqd(fieldname, reqd) {
		this.set_field_property(fieldname, "reqd", reqd ? 1 : 0);
	}
	toggle_display(fieldname, show) {
		this.set_field_property(fieldname, "hidden", show ? 0 : 1);
	}
	toggle_editable(fieldname, editable) {
		this.set_field_property(fieldname, "read_only", editable ? 0 : 1);
	}
}
