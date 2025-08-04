frappe.provide("frappe.views");

frappe.ui.GroupBy = class {
	constructor(report_view) {
		this.report_view = report_view;
		this.page = report_view.page;
		this.doctype = report_view.doctype;
		this.make();
	}

	make() {
		this.make_group_by_button();
		this.init_group_by_popover();
		this.set_popover_events();
	}

	init_group_by_popover() {
		const sql_aggregate_functions = [
			{ name: "count", label: __("Count") },
			{ name: "sum", label: __("Sum") },
			{ name: "avg", label: __("Average") },
		];

		const group_by_template = $(
			frappe.render_template("group_by", {
				doctype: this.doctype,
				group_by_conditions: this.get_group_by_fields(),
				aggregate_function_conditions: sql_aggregate_functions,
			})
		);

		this.group_by_button.popover({
			content: group_by_template,
			template: `
				<div class="group-by-popover popover">
					<div class="arrow"></div>
					<div class="popover-body popover-content">
					</div>
				</div>
			`,
			html: true,
			trigger: "manual",
			container: "body",
			placement: "bottom",
			offset: "-100px, 0",
		});
	}

	// TODO: make common with filter popover
	set_popover_events() {
		$(document.body).on("click", (e) => {
			if (this.wrapper && this.wrapper.is(":visible")) {
				if (
					$(e.target).parents(".group-by-popover").length === 0 &&
					$(e.target).parents(".group-by-box").length === 0 &&
					$(e.target).parents(".group-by-button").length === 0 &&
					!$(e.target).is(this.group_by_button)
				) {
					this.wrapper && this.group_by_button.popover("hide");
				}
			}
		});

		this.group_by_button.on("click", () => {
			this.group_by_button.popover("toggle");
		});

		this.group_by_button.on("shown.bs.popover", () => {
			if (!this.wrapper) {
				this.wrapper = $(".group-by-popover");
				this.setup_group_by_area();
			}
		});

		this.group_by_button.on("hidden.bs.popover", () => {
			this.update_group_by_button();
		});

		frappe.router.on("change", () => {
			this.group_by_button.popover("hide");
		});
	}

	setup_group_by_area() {
		this.aggregate_on_html = ``;
		this.group_by_select = this.wrapper.find("select.group-by");
		this.group_by_field && this.group_by_select.val(this.group_by_field);
		this.aggregate_function_select = this.wrapper.find("select.aggregate-function");
		this.aggregate_on_select = this.wrapper.find("select.aggregate-on");
		this.remove_group_by_button = this.wrapper.find(".remove-group-by");

		if (this.aggregate_function) {
			this.aggregate_function_select.val(this.aggregate_function);
		} else {
			// set default to count
			this.aggregate_function_select.val("count");
			this.aggregate_function = "count";
		}

		this.toggle_aggregate_on_field();
		this.aggregate_on && this.aggregate_on_select.val(this.aggregate_on_field);

		this.set_group_by_events();
	}

	set_group_by_events() {
		// try running on change
		this.group_by_select.on("change", () => {
			this.group_by_field = this.group_by_select.val();
			this.group_by_doctype = this.group_by_select.find(":selected").attr("data-doctype");
			this.apply_group_by_and_refresh();
		});

		this.aggregate_function_select.on("change", () => {
			//Set aggregate on options as numeric fields if function is sum or average
			this.toggle_aggregate_on_field();
			this.aggregate_function = this.aggregate_function_select.val();
			this.apply_group_by_and_refresh();
		});

		this.aggregate_on_select.on("change", () => {
			this.aggregate_on_field = this.aggregate_on_select.val();
			this.aggregate_on_doctype = this.aggregate_on_select
				.find(":selected")
				.attr("data-doctype");
			this.apply_group_by_and_refresh();
		});

		this.remove_group_by_button.on("click", () => {
			if (this.group_by) {
				this.remove_group_by();
				this.toggle_aggregate_on_field_display(false);
			}
		});
	}

	toggle_aggregate_on_field() {
		let fn = this.aggregate_function_select.val();
		if (fn === "sum" || fn === "avg") {
			if (!this.aggregate_on_html.length) {
				this.aggregate_on_html = `<option value="" disabled selected>
						${__("Select Field...")}
					</option>`;

				for (let doctype in this.all_fields) {
					const doctype_fields = this.all_fields[doctype];
					doctype_fields.forEach((field) => {
						// pick numeric fields for sum / avg
						if (frappe.model.is_numeric_field(field.fieldtype)) {
							let field_label = field.label || frappe.model.unscrub(field.fieldname);
							let option_text =
								doctype == this.doctype
									? __(field_label, null, field.parent)
									: `${__(field_label, null, field.parent)} (${__(doctype)})`;
							this.aggregate_on_html += `<option data-doctype="${doctype}"
								value="${field.fieldname}">${option_text}</option>`;
						}
					});
				}
			}
			this.aggregate_on_select.html(this.aggregate_on_html);
			this.toggle_aggregate_on_field_display(true);
		} else {
			// count, so no aggregate function
			this.toggle_aggregate_on_field_display(false);
		}
	}

	//TODO: Fix this
	toggle_aggregate_on_field_display(show) {
		this.group_by_select.parent().toggleClass("col-sm-5", show);
		this.group_by_select.parent().toggleClass("col-sm-8", !show);
		this.aggregate_function_select.parent().toggleClass("col-sm-2", show);
		this.aggregate_function_select.parent().toggleClass("col-sm-3", !show);
		this.aggregate_on_select.parent().toggle(show);
	}

	get_settings() {
		if (this.group_by) {
			return {
				group_by: this.group_by,
				aggregate_function: this.aggregate_function,
				aggregate_on: this.aggregate_on,
			};
		} else {
			return null;
		}
	}

	apply_settings(settings) {
		let get_fieldname = (name) => name.split(".")[1].replace(/`/g, "");
		let get_doctype = (name) => name.split(".")[0].replace(/`/g, "").replace("tab", "");

		if (!settings.group_by.startsWith("`tab")) {
			settings.group_by = "`tab" + this.doctype + "`.`" + settings.group_by + "`";
		}

		if (settings.aggregate_on && !settings.aggregate_on.startsWith("`tab")) {
			const aggregate_on_doctype = this.get_aggregate_on_doctype(settings);
			settings.aggregate_on =
				"`tab" + aggregate_on_doctype + "`.`" + settings.aggregate_on + "`";
		}

		// Extract fieldname from `tabdoctype`.`fieldname`
		this.group_by_field = get_fieldname(settings.group_by);
		this.group_by_doctype = get_doctype(settings.group_by);

		this.aggregate_function = settings.aggregate_function;

		if (settings.aggregate_on) {
			this.aggregate_on_field = get_fieldname(settings.aggregate_on);
			this.aggregate_on_doctype = get_doctype(settings.aggregate_on);
		}

		this.apply_group_by();
		this.update_group_by_button();
	}

	get_aggregate_on_doctype(settings) {
		for (let doctype of Object.keys(this.all_fields)) {
			const dt_fields = this.all_fields[doctype];
			if (dt_fields.find((field) => field.fieldname == settings.aggregate_on)) {
				return doctype;
			}
		}
	}

	make_group_by_button() {
		this.page.wrapper.find(".sort-selector").before(
			$(`<div class="group-by-selector">
				<button class="btn btn-default btn-sm group-by-button ellipsis">
					<span class="group-by-icon button-icon">
						${frappe.utils.icon("es-line-folder-alt")}
					</span>
					<span class="button-label hidden-xs">
						${__("Add Group")}
					</span>
				</button>
			</div>`)
		);

		this.group_by_button = this.page.wrapper.find(".group-by-button");
	}

	apply_group_by() {
		if (
			this.group_by_doctype &&
			this.aggregate_on_doctype &&
			this.aggregate_on_doctype != this.doctype &&
			this.group_by_doctype != this.aggregate_on_doctype
		) {
			frappe.msgprint(
				__("Parent-to-child or child-to-different-child grouping is not allowed.")
			);
			return false;
		}

		this.group_by = "`tab" + this.group_by_doctype + "`.`" + this.group_by_field + "`";

		if (this.aggregate_function === "count") {
			this.aggregate_on_field = null;
			this.aggregate_on_doctype = null;
		} else {
			this.aggregate_on =
				"`tab" + this.aggregate_on_doctype + "`.`" + this.aggregate_on_field + "`";
		}

		//All necessary fields must be set before applying group by
		if (
			!this.group_by ||
			!this.aggregate_function ||
			(!this.aggregate_on_field && this.aggregate_function !== "count")
		) {
			return false;
		}

		return true;
	}

	apply_group_by_and_refresh() {
		if (this.apply_group_by()) {
			this.report_view.refresh();
		}
	}

	set_args(args) {
		if (this.aggregate_function && this.group_by) {
			this.report_view.group_by = this.group_by;
			this.report_view.sort_by = "_aggregate_column";
			this.report_view.sort_order = "desc";

			// save original fields
			if (!this.report_view.fields.map((f) => f[0]).includes("_aggregate_column")) {
				this.original_fields = this.report_view.fields.map((f) => f);
			}

			this.report_view.fields = [[this.group_by_field, this.group_by_doctype]];

			// rebuild fields for group by
			args.fields = this.report_view.get_fields();

			// add aggregate column in both query args and report views
			this.report_view.fields.push([
				"_aggregate_column",
				this.aggregate_on_doctype || this.doctype,
			]);

			// setup columns in datatable
			this.report_view.setup_columns();

			Object.assign(args, {
				with_comment_count: false,
				aggregate_on_field: this.aggregate_on_field || "name",
				aggregate_on_doctype: this.aggregate_on_doctype || this.doctype,
				aggregate_function: this.aggregate_function || "count",
				group_by: this.report_view.group_by || null,
				order_by: "_aggregate_column desc",
			});
		}
	}

	get_group_by_docfield() {
		// called from build_column
		let docfield = {};
		if (this.aggregate_function === "count") {
			docfield = {
				fieldtype: "Int",
				label: __("Count"),
				parent: this.doctype,
				width: 200,
			};
		} else {
			// get properties of "aggregate_on", for example Net Total
			docfield = Object.assign(
				{},
				frappe.meta.docfield_map[this.aggregate_on_doctype][this.aggregate_on_field]
			);

			if (this.aggregate_function === "sum") {
				docfield.label = __("Sum of {0}", [__(docfield.label, null, docfield.parent)]);
			} else {
				if (docfield.fieldtype == "Int") {
					docfield.fieldtype = "Float"; // average of ints can be a float
				}
				docfield.label = __("Average of {0}", [__(docfield.label, null, docfield.parent)]);
			}
		}

		docfield.fieldname = "_aggregate_column";
		return docfield;
	}

	remove_group_by() {
		this.order_by = "";
		this.group_by = null;
		this.group_by_field = null;
		this.report_view.group_by = null;
		this.aggregate_function = "count";
		this.aggregate_on = null;
		this.aggregate_on_field = null;
		this.group_by_select.val("");
		this.aggregate_function_select.val("count");
		this.aggregate_on_select.empty().val("");
		this.aggregate_on_select.parent().hide();

		// restore original fields
		if (this.original_fields) {
			this.report_view.fields = this.original_fields;
		} else {
			this.report_view.set_default_fields();
		}

		this.report_view.setup_columns();
		this.original_fields = null;
		this.report_view.refresh();
	}

	get_group_by_fields() {
		this.group_by_fields = {};
		this.all_fields = {};

		let excluded_fields = ["_liked_by", "idx", "name"];
		const standard_fields = frappe.model.std_fields.filter(
			(df) => !excluded_fields.includes(df.fieldname)
		);

		const fields = this.report_view.meta.fields
			.concat(standard_fields)
			.filter((f) =>
				[
					"Select",
					"Link",
					"Data",
					"Int",
					"Check",
					"Dynamic Link",
					"Autocomplete",
					"Date",
				].includes(f.fieldtype)
			);
		this.group_by_fields[this.doctype] = fields.sort((a, b) =>
			__(cstr(a.label)).localeCompare(cstr(__(b.label)))
		);
		this.all_fields[this.doctype] = this.report_view.meta.fields;

		const standard_fields_filter = (df) =>
			!frappe.model.no_value_type.includes(df.fieldtype) && !df.report_hide;

		const table_fields = frappe.meta.get_table_fields(this.doctype).filter((df) => !df.hidden);

		table_fields.forEach((df) => {
			const cdt = df.options;
			const child_table_fields = frappe.meta
				.get_docfields(cdt)
				.filter(standard_fields_filter)
				.sort((a, b) => __(cstr(a.label)).localeCompare(__(cstr(b.label))));
			this.group_by_fields[cdt] = child_table_fields;
			this.all_fields[cdt] = child_table_fields;
		});

		return this.group_by_fields;
	}

	update_group_by_button() {
		const group_by_applied = Boolean(this.group_by_field);
		const button_label = group_by_applied
			? __("Grouped by <span style='font-weight:600;'>{0}</b>", [
					this.get_group_by_field_label(),
			  ])
			: __("Add Group");

		this.group_by_button
			.toggleClass("btn-default", !group_by_applied)
			.toggleClass("btn-primary-light", group_by_applied);

		this.group_by_button.find(".group-by-icon").toggleClass("active", group_by_applied);

		this.group_by_button.find(".button-label").html(button_label);
		this.group_by_button.attr(
			"title",
			`Results are Grouped by ${this.get_group_by_field_label()}`
		);
	}

	get_group_by_field_label() {
		let field = this.group_by_fields[this.group_by_doctype]?.find(
			(field) => field.fieldname == this.group_by_field
		);
		return field?.label ? __(field.label, null, field.parent) : field?.fieldname;
	}
};
