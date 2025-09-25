frappe.provide("frappe.views");

frappe.ui.GroupBy = class {
	constructor(report_view) {
		this.report_view = report_view;
		this.page = report_view.page;
		this.doctype = report_view.doctype;
		this.group_by_fields = [];
		this.make();
	}

	make() {
		this.make_group_by_button();
		this.init_group_by_popover();
		this.set_popover_events();
	}

	// Initializes the popover with the group by options.
	init_group_by_popover() {
		const sql_aggregate_functions = [
			{ name: "count", label: __("Count") },
			{ name: "sum", label: __("Sum") },
			{ name: "avg", label: __("Average") },
		];

		const group_by_html = frappe.render_template("group_by", {
			doctype: this.doctype,
			group_by_conditions: this.get_group_by_fields(),
			aggregate_function_conditions: sql_aggregate_functions,
		});

		const group_by_template = $(group_by_html);
		this.popover_content = group_by_template.filter(".group-by-box");
		// Get the template for a single group by field from a hidden container.
		this.group_by_field_template = group_by_template
			.filter(".group-by-field-template-container")
			.html();

		this.group_by_button.popover({
			content: this.popover_content,
			template: `
			<div class="group-by-popover popover">
					<div class="arrow"></div>
					<div class="popover-body popover-content">
					</div>
				</div>`,
			html: true,
			trigger: "manual",
			container: "body",
			placement: "bottom",
			offset: "-100px, 0",
		});
	}

	// Sets up the events for the popover.
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
			}
			this.setup_group_by_area();
		});

		this.group_by_button.on("hidden.bs.popover", () => {
			this.update_group_by_button();
		});

		frappe.router.on("change", () => {
			this.group_by_button.popover("hide");
		});
	}

	// Sets up the group by area with the aggregate function and group by fields.
	setup_group_by_area() {
		this.aggregate_on_html = "";
		this.aggregate_function_select = this.wrapper.find("select.aggregate-function");
		this.aggregate_on_select = this.wrapper.find("select.aggregate-on");
		this.group_by_fields_container = this.wrapper.find(".group-by-fields-container");
		this.add_group_by_field_button = this.wrapper.find(".add-group-by-field");
		this.clear_all_button = this.wrapper.find(".clear-all-groups");

		if (this.aggregate_function) {
			this.aggregate_function_select.val(this.aggregate_function);
		} else {
			// set default to count
			this.aggregate_function_select.val("count");
			this.aggregate_function = "count";
		}

		this.toggle_aggregate_on_field();
		if (this.aggregate_on_field) {
			this.aggregate_on_select.val(this.aggregate_on_field);
		}

		this.restore_group_by_fields();
		this.set_group_by_events();
	}

	// Restores the saved group by fields in the popover.
	restore_group_by_fields() {
		this.group_by_fields_container.empty();
		if (this.group_by_fields.length) {
			this.group_by_fields.forEach((field) => {
				this.add_group_by_field(field);
			});
		} else {
			this.add_group_by_field();
		}
	}

	// Adds a new group by field to the popover.
	add_group_by_field(field = null) {
		const $group_by_field = $(this.group_by_field_template);
		this.group_by_fields_container.append($group_by_field);
		if (field) {
			$group_by_field.find("select.group-by").val(field.fieldname);
		}

		$group_by_field.find(".remove-group-by").addClass("text-muted");
		this.update_group_by_options();

		$group_by_field.find(".remove-group-by").on("click", () => {
			if (this.group_by_fields_container.find(".list_groupby").length > 1) {
				$group_by_field.remove();
			} else {
				$group_by_field.find("select.group-by").val("");
			}
			this.update_group_by_options();
			this.apply_group_by_and_refresh();
		});

		$group_by_field.find("select.group-by").on("change", () => {
			this.update_group_by_options();
			this.apply_group_by_and_refresh();
		});
	}

	// Sets up the event handlers for the group by controls.
	set_group_by_events() {
		this.add_group_by_field_button.on("click", () => {
			this.add_group_by_field();
		});

		if (this.clear_all_button) {
			this.clear_all_button.on("click", () => {
				this.remove_group_by();
			});
		}

		this.aggregate_function_select.on("change", () => {
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
	}

	// Shows or hides the aggregate_on field based on the aggregate function.
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
			this.aggregate_on_select.show();
		} else {
			this.aggregate_on_select.hide();
		}
	}

	// Disable fields that are already selected in other group by fields
	update_group_by_options() {
		const selected_fields = [];
		this.wrapper.find("select.group-by").each(function () {
			const value = $(this).val();
			if (value) {
				selected_fields.push(value);
			}
		});

		this.wrapper.find("select.group-by").each(function () {
			const current_select = $(this);
			const current_value = current_select.val();
			current_select.find("option").each(function () {
				const option = $(this);
				const value = option.attr("value");
				const is_selected_elsewhere =
					selected_fields.includes(value) && value !== current_value;
				option.prop("disabled", is_selected_elsewhere);
			});
		});
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

	// Apply the saved group by settings.
	apply_settings(settings) {
		let get_fieldname = (name) => name.split(".")[1].replace(/`/g, "");
		let get_doctype = (name) => name.split(".")[0].replace(/`/g, "").replace("tab", "");

		if (settings.group_by) {
			// Parse the group_by string into an array of fields.
			const fields = settings.group_by.split(",").map((f) => f.trim());
			this.group_by_fields = fields
				.map((f) => ({
					fieldname: get_fieldname(f),
					doctype: get_doctype(f),
				}))
				.filter((f) => f.fieldname);
		}

		this.aggregate_function = settings.aggregate_function;

		if (settings.aggregate_on) {
			if (!settings.aggregate_on.startsWith("`tab")) {
				const aggregate_on_doctype = this.get_aggregate_on_doctype(settings);
				settings.aggregate_on =
					"`tab" + aggregate_on_doctype + "`.`" + settings.aggregate_on + "`";
			}
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
					<span class="group-by-icon">
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

	// Applies the group by settings to the report.
	apply_group_by() {
		let group_bys = [];
		if (this.wrapper && this.wrapper.is(":visible")) {
			this.wrapper.find(".list_groupby").each(function () {
				const group_by_select = $(this).find("select.group-by");
				const fieldname = group_by_select.val();
				if (fieldname) {
					const doctype = group_by_select.find(":selected").data("doctype");
					group_bys.push({ fieldname, doctype });
				}
			});
		} else {
			group_bys = this.group_by_fields || [];
		}

		if (!group_bys.length || !group_bys[0].fieldname) {
			if (this.group_by) this.remove_group_by();
			return false;
		}

		this.group_by_fields = group_bys;

		// Construct the group_by string from the array of fields.
		this.group_by = this.group_by_fields
			.map((field) => {
				return "`tab" + field.doctype + "`.`" + field.fieldname + "`";
			})
			.join(", ");

		if (this.aggregate_function === "count") {
			this.aggregate_on_field = null;
			this.aggregate_on_doctype = null;
			this.aggregate_on = null;
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

			this.report_view.fields = this.group_by_fields.map((f) => [f.fieldname, f.doctype]);

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

	// Removes the group by settings and refreshes the report.
	remove_group_by() {
		this.order_by = "";
		this.group_by = null;
		this.group_by_fields = [];
		this.report_view.group_by = null;
		this.aggregate_function = "count";
		this.aggregate_on = null;
		this.aggregate_on_field = null;

		if (this.wrapper) {
			this.group_by_fields_container.empty();
			this.add_group_by_field();
			this.aggregate_function_select.val("count");
			this.aggregate_on_select.empty().val("");
			this.aggregate_on_select.hide();
		}

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
		this.group_by_fields_map = {};
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
		this.group_by_fields_map[this.doctype] = fields.sort((a, b) =>
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
			this.group_by_fields_map[cdt] = child_table_fields;
			this.all_fields[cdt] = child_table_fields;
		});

		return this.group_by_fields_map;
	}

	// Updates the group by button text and style.
	update_group_by_button() {
		const group_by_applied =
			this.group_by_fields.length > 0 && this.group_by_fields[0].fieldname;
		const button_label = group_by_applied
			? __("Grouped by <span style='font-weight:600;'>{0}</b>,..", [
					this.get_group_by_field_label(this.group_by_fields[0]),
			  ])
			: __("Add Group");

		this.group_by_button
			.toggleClass("btn-default", !group_by_applied)
			.toggleClass("btn-secoundary", group_by_applied);

		this.group_by_button.find(".group-by-icon").toggleClass("active", group_by_applied);

		this.group_by_button.find(".button-label").html(button_label);

		if (group_by_applied) {
			const field_labels = this.group_by_fields
				.map((f) => this.get_group_by_field_label(f))
				.join(", ");
			this.group_by_button.attr("title", `Results are Grouped by ${field_labels}`);
		} else {
			this.group_by_button.attr("title", "Add Group");
		}
	}

	get_group_by_field_label(field) {
		if (!field || !field.doctype || !field.fieldname) return "";
		let docfield = this.group_by_fields_map[field.doctype]?.find(
			(df) => df.fieldname == field.fieldname
		);
		return docfield?.label ? __(docfield.label, null, docfield.parent) : docfield?.fieldname;
	}
};
