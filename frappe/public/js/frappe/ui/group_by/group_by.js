frappe.provide("frappe.views");

frappe.ui.GroupBy = class {
	constructor(report_view) {
		this.report_view = report_view;
		this.page = report_view.page;
		this.doctype = report_view.doctype;
		this.group_by_fields_selected = [];
		this.aggregates = [];
		this.applied_group_bys = [];
		this.applied_aggregates = [];
		this.make();
	}

	make() {
		this.make_group_by_button();
		this.init_group_by_popover();
		this.set_popover_events();
	}

	init_group_by_popover() {
		this.get_group_by_fields();
		this.$group_by_area = $("<div>");
		this.render_group_by_area();
		this.set_group_by_events();

		this.group_by_button.popover({
			content: this.$group_by_area,
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

	render_group_by_area() {
		const group_bys = this.group_by_fields_selected.length
			? this.group_by_fields_selected
			: [{}];

		this.$group_by_area.html(
			frappe.render_template("group_by", {
				doctype: this.doctype,
				group_bys: group_bys,
				aggregates: this.aggregates,
				grouped: this.get_group_bys().length > 0,
				aggregate_function_conditions: [
					{ name: "count", label: __("Count") },
					{ name: "sum", label: __("Sum") },
					{ name: "avg", label: __("Average") },
					{ name: "min", label: __("Minimum") },
					{ name: "max", label: __("Maximum") },
				],
			})
		);

		this.$group_by_area.find(".group-by-field-select").each((i, parent) => {
			const idx = cint($(parent).closest("[data-idx]").attr("data-idx"));
			const { doctype, fieldname } = group_bys[idx];
			this.make_field_select(parent, this.get_group_by_select_fields(), {
				doctype,
				fieldname,
				placeholder: __("Select Group By..."),
				select: (doctype, fieldname) => this.set_group_by_field(idx, doctype, fieldname),
			});
		});

		this.$group_by_area.find(".aggregate-on-field-select").each((i, parent) => {
			const idx = cint($(parent).closest("[data-idx]").attr("data-idx"));
			const aggregate = this.aggregates[idx];
			const fields = this.get_aggregate_on_select_fields(aggregate.aggregate_function);
			this.make_field_select(parent, fields, {
				doctype: aggregate.aggregate_on_doctype,
				fieldname: aggregate.aggregate_on_field,
				placeholder: __("Select Field..."),
				select: (doctype, fieldname) =>
					this.set_aggregate_on_field(idx, doctype, fieldname),
			});
		});
	}

	make_field_select(parent, fields, { doctype, fieldname, placeholder, select }) {
		const field_select = new frappe.ui.FieldSelect({
			parent,
			doctype: this.doctype,
			filter_fields: fields,
			input_class: "input-xs",
			select,
		});
		field_select.$input.attr({ placeholder, "aria-label": placeholder });
		field_select.set_value(doctype, fieldname);
	}

	set_group_by_field(idx, doctype, fieldname) {
		const was_grouped = this.get_group_bys().length > 0;
		this.group_by_fields_selected[idx] = { doctype, fieldname };
		if (!this.aggregates.length) {
			this.aggregates = [{ aggregate_function: "count" }];
		}
		if (!was_grouped) {
			this.render_group_by_area();
		}
		this.apply_group_by_and_refresh();
	}

	set_aggregate_on_field(idx, doctype, fieldname) {
		Object.assign(this.aggregates[idx], {
			aggregate_on_doctype: doctype,
			aggregate_on_field: fieldname,
		});
		this.apply_group_by_and_refresh();
	}

	// TODO: make common with filter popover
	set_popover_events() {
		$(document.body).on("click", (e) => {
			if (this.wrapper && this.wrapper.is(":visible")) {
				if (
					// re-rendering the popover detaches the clicked element
					document.body.contains(e.target) &&
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
		});

		this.group_by_button.on("hidden.bs.popover", () => {
			this.update_group_by_button();
		});

		frappe.router.on("change", () => {
			this.group_by_button.popover("hide");
		});
	}

	set_group_by_events() {
		const get_idx = (e) => cint($(e.target).closest("[data-idx]").attr("data-idx"));

		this.$group_by_area.on("change", "select.aggregate-function", (e) => {
			const aggregate_function = $(e.target).val();
			const aggregate = this.aggregates[get_idx(e)];
			const keeps_field =
				aggregate_function !== "count" &&
				this.get_aggregate_on_select_fields(aggregate_function).some(
					(df) =>
						df.parent === aggregate.aggregate_on_doctype &&
						df.fieldname === aggregate.aggregate_on_field
				);
			this.aggregates[get_idx(e)] = keeps_field
				? { ...aggregate, aggregate_function }
				: { aggregate_function };
			this.render_group_by_area();
			this.apply_group_by_and_refresh();
		});

		this.$group_by_area.on("click", ".add-group-by", () => {
			this.group_by_fields_selected.push({});
			this.render_group_by_area();
		});

		this.$group_by_area.on("click", ".add-aggregate", () => {
			this.aggregates.push({ aggregate_function: "count" });
			this.render_group_by_area();
			this.apply_group_by_and_refresh();
		});

		this.$group_by_area.on("click", ".remove-group-by-row", (e) => {
			this.group_by_fields_selected.splice(get_idx(e), 1);
			if (this.get_group_bys().length) {
				this.render_group_by_area();
				this.apply_group_by_and_refresh();
			} else {
				this.remove_group_by();
			}
		});

		this.$group_by_area.on("click", ".remove-aggregate", (e) => {
			this.aggregates.splice(get_idx(e), 1);
			this.render_group_by_area();
			this.apply_group_by_and_refresh();
		});

		this.$group_by_area.on("click", ".clear-group-by", () => {
			this.remove_group_by();
			this.group_by_button.popover("hide");
		});

		this.$group_by_area.on("click", ".apply-group-by", () => {
			this.group_by_button.popover("hide");
		});
	}

	get_group_by_select_fields() {
		return Object.entries(this.group_by_fields).flatMap(([doctype, fields]) =>
			fields.map((df) => ({ ...df, parent: doctype }))
		);
	}

	get_aggregate_on_select_fields(aggregate_function) {
		const allows_dates = ["min", "max"].includes(aggregate_function);
		return Object.entries(this.all_fields).flatMap(([doctype, fields]) =>
			fields
				.filter(
					(df) =>
						frappe.model.is_numeric_field(df.fieldtype) ||
						(allows_dates && ["Date", "Datetime", "Time"].includes(df.fieldtype))
				)
				.map((df) => ({ ...df, parent: doctype }))
		);
	}

	get_group_bys() {
		return this.group_by_fields_selected.filter((f) => f.fieldname);
	}

	get_aggregates() {
		return this.aggregates.filter(
			(a) => a.aggregate_function === "count" || a.aggregate_on_field
		);
	}

	get_aggregate_fieldname(idx) {
		return idx ? `_aggregate_column_${idx}` : "_aggregate_column";
	}

	get_sql_field(doctype, fieldname) {
		return "`tab" + doctype + "`.`" + fieldname + "`";
	}

	get_settings() {
		if (!this.group_by) {
			return null;
		}

		return {
			group_by: this.applied_group_bys.map((f) =>
				this.get_sql_field(f.doctype, f.fieldname)
			),
			aggregates: this.applied_aggregates.map((a) =>
				a.aggregate_function === "count"
					? { aggregate_function: "count" }
					: {
							aggregate_function: a.aggregate_function,
							aggregate_on: this.get_sql_field(
								a.aggregate_on_doctype,
								a.aggregate_on_field
							),
					  }
			),
		};
	}

	normalize_settings(settings) {
		if (settings.aggregates) {
			return settings;
		}

		const aggregate = { aggregate_function: settings.aggregate_function };
		// legacy settings may keep a stale aggregate_on for count
		if (settings.aggregate_on && settings.aggregate_function !== "count") {
			aggregate.aggregate_on = settings.aggregate_on;
		}
		return { group_by: [settings.group_by], aggregates: [aggregate] };
	}

	apply_settings(settings) {
		settings = this.normalize_settings(settings);
		let get_fieldname = (name) => name.split(".")[1].replace(/`/g, "");
		let get_doctype = (name) => name.split(".")[0].replace(/`/g, "").replace(/^tab/, "");

		this.group_by_fields_selected = settings.group_by.map((group_by) =>
			group_by.startsWith("`tab")
				? { fieldname: get_fieldname(group_by), doctype: get_doctype(group_by) }
				: { fieldname: group_by, doctype: this.doctype }
		);

		this.aggregates = settings.aggregates.map((aggregate) => {
			const aggregate_on = aggregate.aggregate_on;
			if (!aggregate_on) {
				return { aggregate_function: aggregate.aggregate_function };
			}
			return {
				aggregate_function: aggregate.aggregate_function,
				aggregate_on_field: aggregate_on.startsWith("`tab")
					? get_fieldname(aggregate_on)
					: aggregate_on,
				aggregate_on_doctype: aggregate_on.startsWith("`tab")
					? get_doctype(aggregate_on)
					: this.get_aggregate_on_doctype(aggregate_on),
			};
		});

		this.apply_group_by();
		this.render_group_by_area();
		this.update_group_by_button();
	}

	get_aggregate_on_doctype(fieldname) {
		for (let doctype of Object.keys(this.all_fields)) {
			const dt_fields = this.all_fields[doctype];
			if (dt_fields.find((field) => field.fieldname == fieldname)) {
				return doctype;
			}
		}
	}

	make_group_by_button() {
		this.page.wrapper.find(".sort-selector").before(
			$(`<div class="group-by-selector">
				<div class="btn-group">
					<button class="btn btn-default btn-sm group-by-button ellipsis">
						<span class="group-by-icon button-icon">
							${frappe.utils.icon("folder")}
						</span>
						<span class="button-label hidden-xs">
							${__("Add Group")}
						</span>
					</button>
					<button class="btn btn-default btn-sm group-by-x-button" title="${__("Clear Grouping")}">
						<span class="button-icon">
							${frappe.utils.icon("x")}
						</span>
					</button>
				</div>
			</div>`)
		);

		this.group_by_button = this.page.wrapper.find(".group-by-button");
		this.group_by_x_button = this.page.wrapper.find(".group-by-x-button");
		this.group_by_x_button.on("click", () => {
			// without a grouping there is nothing to clear, and removing would reset the columns
			if (this.group_by) this.remove_group_by();
		});
	}

	apply_group_by() {
		const group_bys = this.get_group_bys();
		const aggregates = this.get_aggregates();
		const child_doctypes = new Set(
			group_bys
				.map((f) => f.doctype)
				.concat(aggregates.map((a) => a.aggregate_on_doctype))
				.filter((doctype) => doctype && doctype !== this.doctype)
		);
		if (child_doctypes.size > 1) {
			frappe.msgprint(__("Group By and aggregate fields can only use one child table."));
			this.group_by_fields_selected = this.applied_group_bys.map((f) => ({ ...f }));
			this.aggregates = this.applied_aggregates.map((a) => ({ ...a }));
			this.render_group_by_area();
			return false;
		}

		// only complete selections reach the query, half-edited rows stay in the popover
		if (!group_bys.length || aggregates.length !== this.aggregates.length) {
			return false;
		}

		this.applied_group_bys = group_bys.map((f) => ({ ...f }));
		this.applied_aggregates = aggregates.map((a) => ({ ...a }));
		this.group_by = group_bys
			.map((f) => this.get_sql_field(f.doctype, f.fieldname))
			.join(", ");
		return true;
	}

	apply_group_by_and_refresh() {
		if (this.apply_group_by()) {
			this.report_view.refresh();
		}
	}

	set_args(args) {
		if (!this.group_by) {
			return;
		}

		this.report_view.group_by = this.group_by;
		this.report_view.sort_by = "_aggregate_column";
		this.report_view.sort_order = "desc";

		// save original fields
		if (!this.report_view.fields.map((f) => f[0]).includes("_aggregate_column")) {
			this.original_fields = this.report_view.fields.map((f) => f);
		}

		this.report_view.fields = this.applied_group_bys.map((f) => [f.fieldname, f.doctype]);

		// rebuild fields for group by
		args.fields = this.report_view.get_fields();

		// add aggregate columns in both query args and report views
		this.applied_aggregates.forEach((aggregate, idx) => {
			const fieldname = this.get_aggregate_fieldname(idx);
			const doctype = aggregate.aggregate_on_doctype || this.doctype;
			const aggregate_on = this.get_sql_field(
				doctype,
				aggregate.aggregate_on_field || "name"
			);

			args.fields.push({
				[aggregate.aggregate_function.toUpperCase()]: aggregate_on,
				as: fieldname,
			});
			this.report_view.fields.push([fieldname, doctype]);
		});

		// setup columns in datatable
		this.report_view.setup_columns();

		Object.assign(args, {
			with_comment_count: false,
			group_by: this.group_by,
			order_by: "_aggregate_column desc",
		});
	}

	get_group_by_docfield(fieldname) {
		// called from build_column
		const idx = fieldname === "_aggregate_column" ? 0 : cint(fieldname.split("_").pop());
		const aggregate = this.applied_aggregates[idx];

		let docfield = {};
		if (aggregate.aggregate_function === "count") {
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
				frappe.meta.docfield_map[aggregate.aggregate_on_doctype][
					aggregate.aggregate_on_field
				]
			);

			if (aggregate.aggregate_function === "sum") {
				docfield.label = __("Sum of {0}", [__(docfield.label, null, docfield.parent)]);
			} else if (aggregate.aggregate_function === "min") {
				docfield.label = __("Minimum of {0}", [__(docfield.label, null, docfield.parent)]);
			} else if (aggregate.aggregate_function === "max") {
				docfield.label = __("Maximum of {0}", [__(docfield.label, null, docfield.parent)]);
			} else {
				if (docfield.fieldtype == "Int") {
					docfield.fieldtype = "Float"; // average of ints can be a float
				}
				docfield.label = __("Average of {0}", [__(docfield.label, null, docfield.parent)]);
			}

			if (
				docfield.fieldtype == "Currency" &&
				docfield.options &&
				!docfield.options.includes(":") &&
				!this.applied_group_bys.some((f) => f.fieldname == docfield.options)
			) {
				docfield.precision = frappe.meta.get_field_precision(docfield);
				docfield.fieldtype = "Float";
				docfield.options = null;
			}
		}

		docfield.fieldname = fieldname;
		return docfield;
	}

	remove_group_by() {
		this.order_by = "";
		this.group_by = null;
		this.report_view.group_by = null;
		this.group_by_fields_selected = [];
		this.aggregates = [];
		this.applied_group_bys = [];
		this.applied_aggregates = [];
		this.render_group_by_area();

		// restore original fields
		if (this.original_fields) {
			this.report_view.fields = this.original_fields;
		} else {
			this.report_view.set_default_fields();
		}

		this.report_view.setup_columns();
		this.original_fields = null;
		this.report_view.refresh();
		this.update_group_by_button();
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
			.filter(
				(f) =>
					[
						"Select",
						"Link",
						"Data",
						"Int",
						"Check",
						"Dynamic Link",
						"Autocomplete",
						"Date",
					].includes(f.fieldtype) && !f.is_virtual
			);
		this.group_by_fields[this.doctype] = fields.sort((a, b) =>
			__(cstr(a.label)).localeCompare(cstr(__(b.label)))
		);
		this.all_fields[this.doctype] = this.report_view.meta.fields;

		const standard_fields_filter = (df) =>
			!frappe.model.no_value_type.includes(df.fieldtype) &&
			!df.report_hide &&
			!df.is_virtual;

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
		const group_by_applied = Boolean(this.group_by);
		const group_by_labels = this.get_group_by_field_labels();
		const button_label = group_by_applied
			? __("Grouped by <span style='font-weight:600;'>{0}</b>", [group_by_labels])
			: __("Add Group");
		if (group_by_applied) {
			this.group_by_button.find(".button-label").css("gap", "4px");
		}
		this.group_by_button
			.toggleClass("btn-default", !group_by_applied)
			.toggleClass("btn-primary-light", group_by_applied);

		this.group_by_button.find(".group-by-icon").toggleClass("active", group_by_applied);

		this.group_by_button.find(".button-label").html(button_label);
		this.group_by_button.attr("title", __("Results are Grouped by {0}", [group_by_labels]));
	}

	get_group_by_field_labels() {
		return this.applied_group_bys
			.map((group_by) => {
				let field = this.group_by_fields[group_by.doctype]?.find(
					(field) => field.fieldname == group_by.fieldname
				);
				return field?.label ? __(field.label, null, field.parent) : group_by.fieldname;
			})
			.join(", ");
	}
};
