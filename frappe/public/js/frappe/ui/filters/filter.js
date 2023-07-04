frappe.ui.Filter = class {
	constructor(opts) {
		$.extend(this, opts);
		if (this.value === null || this.value === undefined) {
			this.value = "";
		}

		this.utils = frappe.ui.filter_utils;
		this.set_conditions();
		this.set_conditions_from_config();
		this.make();
	}

	set_conditions() {
		this.conditions = [
			["=", __("Equals")],
			["!=", __("Not Equals")],
			["like", __("Like")],
			["not like", __("Not Like")],
			["in", __("In")],
			["not in", __("Not In")],
			["is", __("Is")],
			[">", ">"],
			["<", "<"],
			[">=", ">="],
			["<=", "<="],
			["Between", __("Between")],
			["Timespan", __("Timespan")],
		];

		this.nested_set_conditions = [
			["descendants of", __("Descendants Of")],
			["not descendants of", __("Not Descendants Of")],
			["ancestors of", __("Ancestors Of")],
			["not ancestors of", __("Not Ancestors Of")],
		];

		this.conditions.push(...this.nested_set_conditions);

		this.invalid_condition_map = {
			Date: ["like", "not like"],
			Datetime: ["like", "not like", "in", "not in", "=", "!="],
			Data: ["Between", "Timespan"],
			Select: ["like", "not like", "Between", "Timespan"],
			Link: ["Between", "Timespan", ">", "<", ">=", "<="],
			Currency: ["Between", "Timespan"],
			Color: ["Between", "Timespan"],
			Check: this.conditions.map((c) => c[0]).filter((c) => c !== "="),
			Code: ["Between", "Timespan", ">", "<", ">=", "<=", "in", "not in"],
			"HTML Editor": ["Between", "Timespan", ">", "<", ">=", "<=", "in", "not in"],
			"Markdown Editor": ["Between", "Timespan", ">", "<", ">=", "<=", "in", "not in"],
			Password: ["Between", "Timespan", ">", "<", ">=", "<=", "in", "not in"],
			Rating: ["like", "not like", "Between", "in", "not in", "Timespan"],
		};
	}

	set_conditions_from_config() {
		if (frappe.boot.additional_filters_config) {
			this.filters_config = frappe.boot.additional_filters_config;
			for (let key of Object.keys(this.filters_config)) {
				const filter = this.filters_config[key];
				this.conditions.push([key, __(filter.label)]);
				for (let fieldtype of Object.keys(this.invalid_condition_map)) {
					if (!filter.valid_for_fieldtypes.includes(fieldtype)) {
						this.invalid_condition_map[fieldtype].push(key);
					}
				}
			}
		}
	}

	make() {
		this.filter_edit_area = $(
			frappe.render_template("edit_filter", {
				conditions: this.conditions,
			})
		);
		this.parent && this.filter_edit_area.appendTo(this.parent.find(".filter-edit-area"));
		this.make_select();
		this.set_events();
		this.setup();
	}

	make_select() {
		this.fieldselect = new frappe.ui.FieldSelect({
			parent: this.filter_edit_area.find(".fieldname-select-area"),
			doctype: this.parent_doctype,
			parent_doctype: this._parent_doctype,
			filter_fields: this.filter_fields,
			input_class: "input-xs",
			select: (doctype, fieldname) => {
				this.set_field(doctype, fieldname);
			},
		});

		if (this.fieldname) {
			this.fieldselect.set_value(this.doctype, this.fieldname);
		}
	}

	set_events() {
		this.filter_edit_area.find(".remove-filter").on("click", () => {
			this.remove();
			this.on_change();
		});

		this.filter_edit_area.find(".condition").change(() => {
			if (!this.field) return;

			let condition = this.get_condition();
			let fieldtype = null;

			if (["in", "like", "not in", "not like"].includes(condition)) {
				fieldtype = "Data";
				this.add_condition_help(condition);
			} else {
				this.filter_edit_area.find(".filter-description").empty();
			}

			if (
				["Select", "MultiSelect"].includes(this.field.df.fieldtype) &&
				["in", "not in"].includes(condition)
			) {
				fieldtype = "MultiSelect";
			}

			this.set_field(this.field.df.parent, this.field.df.fieldname, fieldtype, condition);
		});
	}

	setup() {
		const fieldname = this.fieldname || "name";
		// set the field
		return this.set_values(this.doctype, fieldname, this.condition, this.value);
	}

	setup_state(is_new) {
		let promise = Promise.resolve();
		if (is_new) {
			this.filter_edit_area.addClass("new-filter");
		} else {
			promise = this.update_filter_tag();
		}

		if (this.hidden) {
			promise.then(() => this.$filter_tag.hide());
		}
	}

	freeze() {
		this.update_filter_tag();
	}

	update_filter_tag() {
		if (this._filter_value_set) {
			return this._filter_value_set.then(() => {
				!this.$filter_tag ? this.make_tag() : this.set_filter_button_text();
				this.filter_edit_area.hide();
			});
		} else {
			return Promise.resolve();
		}
	}

	remove() {
		this.filter_edit_area.remove();
		this.field = null;
		// this.on_change(true);
	}

	set_values(doctype, fieldname, condition, value) {
		// presents given (could be via tags!)
		if (this.set_field(doctype, fieldname) === false) {
			return;
		}

		if (this.field.df.original_type === "Check") {
			value = value == 1 ? "Yes" : "No";
		}
		if (condition) this.set_condition(condition, true);

		// set value can be asynchronous, so update_filter_tag should happen after field is set
		this._filter_value_set = Promise.resolve();

		if (["in", "not in"].includes(condition) && Array.isArray(value)) {
			value = value.join(",");
		}

		if (Array.isArray(value)) {
			this._filter_value_set = this.field.set_value(value);
		} else if (value !== undefined || value !== null) {
			this._filter_value_set = this.field.set_value((value + "").trim());
		}
		return this._filter_value_set;
	}

	set_field(doctype, fieldname, fieldtype, condition) {
		// set in fieldname (again)
		let cur = {};
		if (this.field) for (let k in this.field.df) cur[k] = this.field.df[k];

		let original_docfield = (this.fieldselect.fields_by_name[doctype] || {})[fieldname];

		if (!original_docfield) {
			console.warn(`Field ${fieldname} is not selectable.`);
			this.remove();
			return false;
		}

		let df = copy_dict(original_docfield);

		// filter field shouldn't be read only or hidden
		df.read_only = 0;
		df.hidden = 0;
		df.is_filter = true;
		delete df.hidden_due_to_dependency;

		let c = condition ? condition : this.utils.get_default_condition(df);
		this.set_condition(c);

		this.utils.set_fieldtype(df, fieldtype, this.get_condition());

		// called when condition is changed,
		// don't change if all is well
		if (
			this.field &&
			cur.fieldname == fieldname &&
			df.fieldtype == cur.fieldtype &&
			df.parent == cur.parent &&
			df.options == cur.options
		) {
			return;
		}

		// clear field area and make field
		this.fieldselect.selected_doctype = doctype;
		this.fieldselect.selected_fieldname = fieldname;

		if (
			this.filters_config &&
			this.filters_config[condition] &&
			this.filters_config[condition].valid_for_fieldtypes.includes(df.fieldtype)
		) {
			let args = {};
			if (this.filters_config[condition].depends_on) {
				const field_name = this.filters_config[condition].depends_on;
				const filter_value = this.filter_list.get_filter_value(fieldname);
				args[field_name] = filter_value;
			}
			let setup_field = (field) => {
				df.fieldtype = field.fieldtype;
				df.options = field.options;
				df.fieldname = fieldname;
				this.make_field(df, cur.fieldtype);
			};
			if (this.filters_config[condition].data) {
				let field = this.filters_config[condition].data;
				setup_field(field);
			} else {
				frappe.xcall(this.filters_config[condition].get_field, args).then((field) => {
					this.filters_config[condition].data = field;
					setup_field(field);
				});
			}
		} else {
			this.make_field(df, cur.fieldtype);
		}
	}

	make_field(df, old_fieldtype) {
		let old_text = this.field ? this.field.get_value() : null;
		this.hide_invalid_conditions(df.fieldtype, df.original_type);
		this.toggle_nested_set_conditions(df);
		let field_area = this.filter_edit_area.find(".filter-field").empty().get(0);
		df.input_class = "input-xs";
		let f = frappe.ui.form.make_control({
			df: df,
			parent: field_area,
			only_input: true,
		});
		f.refresh();

		this.field = f;
		if (old_text && f.fieldtype === old_fieldtype) {
			this.field.set_value(old_text);
		}

		this.bind_filter_field_events();
	}

	bind_filter_field_events() {
		// Apply filter on input focus out
		this.field.$input.on("focusout", () => this.on_change());

		// run on enter
		$(this.field.wrapper)
			.find(":input")
			.keydown((e) => {
				if (e.which == 13 && this.field.df.fieldtype !== "MultiSelect") {
					this.on_change();
				}
			});
	}

	get_value() {
		return [
			this.fieldselect.selected_doctype,
			this.field.df.fieldname,
			this.get_condition(),
			this.get_selected_value(),
			this.hidden,
		];
	}

	get_selected_value() {
		return this.utils.get_selected_value(this.field, this.get_condition());
	}

	get_selected_label() {
		return this.utils.get_selected_label(this.field);
	}

	get_condition() {
		return this.filter_edit_area.find(".condition").val();
	}

	set_condition(condition, trigger_change = false) {
		let $condition_field = this.filter_edit_area.find(".condition");
		$condition_field.val(condition);
		if (trigger_change) $condition_field.change();
	}

	add_condition_help(condition) {
		const description = ["in", "not in"].includes(condition)
			? __("values separated by commas")
			: __("use % as wildcard");

		this.filter_edit_area.find(".filter-description").html(description);
	}

	make_tag() {
		if (!this.field) return;
		this.$filter_tag = this.get_filter_tag_element().insertAfter(
			this.parent.find(".active-tag-filters .clear-filters")
		);
		this.set_filter_button_text();
		this.bind_tag();
	}

	bind_tag() {
		this.$filter_tag.find(".remove-filter").on("click", this.remove.bind(this));

		let filter_button = this.$filter_tag.find(".toggle-filter");
		filter_button.on("click", () => {
			filter_button.closest(".tag-filters-area").find(".filter-edit-area").show();
			this.filter_edit_area.toggle();
		});
	}

	set_filter_button_text() {
		this.$filter_tag.find(".toggle-filter").html(this.get_filter_button_text());
	}

	get_filter_button_text() {
		let value = this.utils.get_formatted_value(
			this.field,
			this.get_selected_label() || this.get_selected_value()
		);
		return `${__(this.field.df.label)} ${__(this.get_condition())} ${__(value)}`;
	}

	get_filter_tag_element() {
		return $(`<div class="filter-tag btn-group">
			<button class="btn btn-default btn-xs toggle-filter"
				title="${__("Edit Filter")}">
			</button>
			<button class="btn btn-default btn-xs remove-filter"
				title="${__("Remove Filter")}">
				${frappe.utils.icon("close")}
			</button>
		</div>`);
	}

	hide_invalid_conditions(fieldtype, original_type) {
		let invalid_conditions =
			this.invalid_condition_map[original_type] ||
			this.invalid_condition_map[fieldtype] ||
			[];

		for (let condition of this.conditions) {
			this.filter_edit_area
				.find(`.condition option[value="${condition[0]}"]`)
				.toggle(!invalid_conditions.includes(condition[0]));
		}
	}

	toggle_nested_set_conditions(df) {
		let show_condition =
			df.fieldtype === "Link" && frappe.boot.nested_set_doctypes.includes(df.options);
		this.nested_set_conditions.forEach((condition) => {
			this.filter_edit_area
				.find(`.condition option[value="${condition[0]}"]`)
				.toggle(show_condition);
		});
	}
};

frappe.ui.filter_utils = {
	get_formatted_value(field, value) {
		if (field.df.fieldname === "docstatus") {
			value = { 0: "Draft", 1: "Submitted", 2: "Cancelled" }[value] || value;
		} else if (field.df.original_type === "Check") {
			value = { 0: "No", 1: "Yes" }[cint(value)];
		}
		return frappe.format(value, field.df, { only_value: 1 });
	},

	get_selected_value(field, condition) {
		if (!field) return;

		let val = field.get_value() || field.value;

		if (typeof val === "string") {
			val = strip(val);
		}

		if (condition == "is" && !val) {
			val = field.df.options[0].value;
		}

		if (field.df.original_type == "Check") {
			val = val == "Yes" ? 1 : 0;
		}

		if (["like", "not like"].includes(condition)) {
			// automatically append wildcards
			if (val && !(val.startsWith("%") || val.endsWith("%"))) {
				val = "%" + val + "%";
			}
		} else if (["in", "not in"].includes(condition)) {
			if (val) {
				val = val.split(",").map((v) => strip(v));
			}
		} else if (frappe.boot.additional_filters_config[condition]) {
			val = field.value || val;
		}
		if (val === "%") {
			val = "";
		}

		return val;
	},

	get_selected_label(field) {
		if (in_list(["Link", "Dynamic Link"], field.df.fieldtype)) {
			return field.get_label_value();
		}
	},

	get_default_condition(df) {
		if (df.fieldtype == "Data") {
			return "like";
		} else if (df.fieldtype == "Date" || df.fieldtype == "Datetime") {
			return "Between";
		} else {
			return "=";
		}
	},

	set_fieldtype(df, fieldtype, condition) {
		// reset
		if (df.original_type) df.fieldtype = df.original_type;
		else df.original_type = df.fieldtype;

		df.description = "";
		df.reqd = 0;
		df.ignore_link_validation = true;

		// given
		if (fieldtype) {
			df.fieldtype = fieldtype;
			return;
		}

		// scrub
		if (df.fieldname == "docstatus") {
			df.fieldtype = "Select";
			df.options = [
				{ value: 0, label: __("Draft") },
				{ value: 1, label: __("Submitted") },
				{ value: 2, label: __("Cancelled") },
			];
		} else if (df.fieldtype == "Check") {
			df.fieldtype = "Select";
			df.options = [
				{ label: __("Yes", null, "Checkbox is checked"), value: "Yes" },
				{ label: __("No", null, "Checkbox is not checked"), value: "No" },
			];
		} else if (
			[
				"Text",
				"Small Text",
				"Text Editor",
				"Code",
				"Attach",
				"Attach Image",
				"Markdown Editor",
				"HTML Editor",
				"Tag",
				"Phone",
				"JSON",
				"Comments",
				"Barcode",
				"Dynamic Link",
				"Read Only",
				"Assign",
				"Color",
			].indexOf(df.fieldtype) != -1
		) {
			df.fieldtype = "Data";
		} else if (
			df.fieldtype == "Link" &&
			[
				"=",
				"!=",
				"descendants of",
				"ancestors of",
				"not descendants of",
				"not ancestors of",
			].indexOf(condition) == -1
		) {
			df.fieldtype = "Data";
		}
		if (df.fieldtype === "Data" && (df.options || "").toLowerCase() === "email") {
			df.options = null;
		}
		if (condition == "Between" && (df.fieldtype == "Date" || df.fieldtype == "Datetime")) {
			df.fieldtype = "DateRange";
		}
		if (
			condition == "Timespan" &&
			["Date", "Datetime", "DateRange", "Select"].includes(df.fieldtype)
		) {
			df.fieldtype = "Select";
			df.options = this.get_timespan_options([
				"Last",
				"Yesterday",
				"Today",
				"Tomorrow",
				"This",
				"Next",
			]);
		}
		if (condition === "is") {
			df.fieldtype = "Select";
			df.options = [
				{ label: __("Set", null, "Field value is set"), value: "set" },
				{ label: __("Not Set", null, "Field value is not set"), value: "not set" },
			];
		}
		return;
	},

	get_timespan_options(periods) {
		const period_map = {
			Last: ["Week", "Month", "Quarter", "6 months", "Year"],
			This: ["Week", "Month", "Quarter", "Year"],
			Next: ["Week", "Month", "Quarter", "6 months", "Year"],
		};
		let options = [];
		periods.forEach((period) => {
			if (period_map[period]) {
				period_map[period].forEach((p) => {
					options.push({
						label: `${period} ${p}`,
						value: `${period.toLowerCase()} ${p.toLowerCase()}`,
					});
				});
			} else {
				options.push({
					label: __(period),
					value: `${period.toLowerCase()}`,
				});
			}
		});
		return options;
	},
};
