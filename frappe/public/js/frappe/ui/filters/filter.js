// One filter row: field picker, condition dropdown, value control, remove.
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
			["!=", __("Not equals")],
			["like", __("Like")],
			["not like", __("Not like")],
			["in", __("In")],
			["not in", __("Not in")],
			["is", __("Is")],
			[">", __("Greater than")],
			["<", __("Less than")],
			[">=", __("Greater than or equal to")],
			["<=", __("Less than or equal to")],
			["Between", __("Between")],
			["Timespan", __("Timespan")],
		];

		this.nested_set_conditions = [
			["descendants of", __("Descendants of")],
			["descendants of (inclusive)", __("Descendants of (inclusive)")],
			["not descendants of", __("Not descendants of")],
			["ancestors of", __("Ancestors of")],
			["not ancestors of", __("Not ancestors of")],
		];

		this.conditions.push(...this.nested_set_conditions);

		this.special_condition_labels = {
			Date: {
				"<": __("Before"),
				">": __("After"),
				"<=": __("On or before"),
				">=": __("On or after"),
			},
			Datetime: {
				"<": __("Before"),
				">": __("After"),
				"<=": __("On or before"),
				">=": __("On or after"),
			},
		};

		this.set_invalid_conditions_map();
	}

	set_invalid_conditions_map() {
		this.range_conditions = ["Between", "Timespan"];
		this.comparison_conditions = [">", "<", ">=", "<="];
		this.like_conditions = ["like", "not like"];
		this.in_conditions = ["in", "not in"];
		this.equality_conditions = ["=", "!="];

		const text_fields = [
			"Code",
			"HTML Editor",
			"Markdown Editor",
			"Text Editor",
			"Small Text",
			"Long Text",
			"Text",
			"Password",
		];

		const numeric_fields = ["Rating", "Int", "Float", "Percent"];

		const text_invalid_conditions = [
			...this.range_conditions,
			...this.comparison_conditions,
			...this.in_conditions,
		];

		const numeric_invalid_conditions = [
			...this.like_conditions,
			...this.range_conditions,
			...this.in_conditions,
		];

		this.invalid_condition_map = {
			Date: this.like_conditions,
			Time: this.range_conditions,
			Data: this.range_conditions,
			Currency: this.range_conditions,

			Link: [...this.range_conditions, ...this.comparison_conditions],
			Color: [...this.range_conditions, ...this.comparison_conditions],

			Datetime: [
				...this.like_conditions,
				...this.in_conditions,
				...this.equality_conditions,
			],
			Select: [
				...this.like_conditions,
				...this.range_conditions,
				...this.comparison_conditions,
			],

			Check: this.conditions
				.map(([condition]) => condition)
				.filter((condition) => condition !== "="),

			...Object.fromEntries(
				text_fields.map((field) => [field, [...text_invalid_conditions]])
			),

			...Object.fromEntries(
				numeric_fields.map((field) => [field, [...numeric_invalid_conditions]])
			),
		};

		// conditions where a Dynamic Link can resolve to a real Link picker
		this.link_friendly_conditions = new Set([
			...this.equality_conditions,
			...this.nested_set_conditions.map(([cond]) => cond),
		]);
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
		this.filter_edit_area = $(`
			<div class="filter-box" role="group">
				<span class="filter-prefix text-ink-gray-5"></span>
				<div class="fieldname-select-area min-w-0"></div>
				<div class="filter-condition min-w-0"></div>
				<div class="filter-field-area min-w-0">
					<div class="filter-field"></div>
				</div>
				<div class="filter-remove"></div>
			</div>`);
		this.parent && this.filter_edit_area.appendTo(this.parent.find(".filter-edit-area"));
		this.make_select();
		this.make_condition();
		this.make_remove_button();
		this.setup();
	}

	make_select() {
		this.fieldselect = new frappe.ui.FieldSelect({
			parent: this.filter_edit_area.find(".fieldname-select-area"),
			doctype: this.parent_doctype,
			parent_doctype: this._parent_doctype,
			filter_fields: this.filter_fields,
			select: (doctype, fieldname) => {
				if (this.set_field(doctype, fieldname) === false) return;
				this.on_change();
				// on phones focus would pop the keyboard up over the sheet
				if (!frappe.is_mobile()) this.focus_value();
			},
		});

		if (this.fieldname) {
			this.fieldselect.set_value(this.doctype, this.fieldname);
		}
	}

	make_condition() {
		// a label so the button renders its label span; set_condition retexts it
		this.$condition = frappe.ui.button({
			label: __("Equals"),
			icon_right: "chevron-down",
			css_class: "condition w-full justify-between",
		});
		this.condition_dropdown = new frappe.ui.Dropdown({
			trigger: this.$condition,
			options: () => this.get_condition_options(),
		});
		this.filter_edit_area.find(".filter-condition").append(this.$condition);
	}

	make_remove_button() {
		const $remove = frappe.ui.button({
			icon: "x",
			variant: "ghost",
			title: __("Remove filter"),
			css_class: "remove-filter",
			onclick: () => {
				this.remove();
				this.on_change();
			},
		});
		this.filter_edit_area.find(".filter-remove").append($remove);
	}

	get_condition_options() {
		const invalid = this.invalid_conditions || [];
		const nested = this.nested_set_conditions.map(([c]) => c);
		return this.conditions
			.filter(([c]) => !invalid.includes(c))
			.filter(([c]) => this.show_nested_set || !nested.includes(c))
			.map(([c]) => ({
				label: this.get_condition_label(c),
				selected: c === this.condition,
				onclick: () => {
					if (c === this.condition) return;
					this.set_condition(c, true);
					this.on_change();
				},
			}));
	}

	get_condition_label(condition) {
		const special = this.special_labels || {};
		if (special[condition]) return special[condition];
		const entry = this.conditions.find(([c]) => c === condition);
		return entry ? entry[1] : __(condition);
	}

	get_condition() {
		return this.condition;
	}

	set_condition(condition, trigger_change = false) {
		this.condition = condition;
		this.$condition.find(".es-button__label").text(this.get_condition_label(condition));
		if (trigger_change) this.on_condition_change();
	}

	on_condition_change() {
		if (!this.field) return;

		const condition = this.get_condition();
		const in_condition = ["in", "not in"].includes(condition);
		let fieldtype = null;

		if (["in", "like", "not in", "not like"].includes(condition)) {
			const is_user_array = ["_assign", "_liked_by"].includes(this.field.df.fieldname);
			if (!(is_user_array && ["like", "not like"].includes(condition))) {
				fieldtype = "Data";
			}
		}

		if (["Select", "MultiSelect"].includes(this.field.df.fieldtype) && in_condition) {
			fieldtype = "MultiSelect";
		}

		// pick several records instead of typing names separated by commas
		if (this.field.df.original_type === "Link" && in_condition) {
			fieldtype = "MultiSelectList";
		}

		this.set_field(this.field.df.parent, this.field.df.fieldname, fieldtype, condition);

		this.get_filter_group()?.refresh_dynamic_link_filters?.();
	}

	set_prefix(text) {
		this.filter_edit_area.find(".filter-prefix").text(text);
	}

	// a row without a field yet keeps its shape: condition and value wait, greyed, for one
	toggle_controls(show) {
		this.filter_edit_area.toggleClass("is-empty", !show);
		this.$condition.prop("disabled", !show);
		if (!show) {
			const $value = $('<input class="form-control" disabled>').attr({
				placeholder: __("Value"),
				"aria-label": __("Value"),
			});
			this.filter_edit_area.find(".filter-field").empty().append($value);
		}
	}

	is_empty() {
		return !this.field;
	}

	focus_value() {
		const input = this.field?.$input || $(this.field?.wrapper).find(":input").first();
		input && input.focus();
	}

	setup() {
		if (!this.fieldname) {
			this.toggle_controls(false);
			return Promise.resolve();
		}
		return this.set_values(this.doctype, this.fieldname, this.condition, this.value);
	}

	remove() {
		this.condition_dropdown?.destroy();
		this.fieldselect?.combobox?.close("owner");
		this.filter_edit_area.remove();
		this.destroy_calendar();
		this.field = null;
	}

	// a date control's calendar is mounted in <body>, so it outlives the row unless removed
	destroy_calendar() {
		this.field?.datepicker?.destroy();
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

		if (
			["in", "not in"].includes(condition) &&
			Array.isArray(value) &&
			this.field.df.fieldtype !== "MultiSelectList"
		) {
			value = value.some((v) => String(v).includes(","))
				? JSON.stringify(value)
				: value.join(",");
		}

		if (Array.isArray(value)) {
			this._filter_value_set = this.field.set_value(value);
		} else if (value !== undefined && value !== null) {
			const field_value = typeof value === "number" ? value : String(value).trim();
			this._filter_value_set = this.field.set_value(field_value);
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

		this.resolve_dynamic_link(df, original_docfield);

		// called when condition is changed,
		// don't change if all is well
		if (
			this.field &&
			cur.fieldname == fieldname &&
			df.fieldtype == cur.fieldtype &&
			df.parent == cur.parent &&
			df.options == cur.options
		) {
			// same box, but its hint follows the condition (Like → Equals → In)
			if (!this.field.df.dynamic_link_hint) {
				this.field.df.placeholder = this.get_placeholder(
					this.field.df,
					this.get_condition()
				);
				this.field.$input?.attr("placeholder", this.field.df.placeholder);
			}
			return;
		}

		// clear field area and make field
		this.fieldselect.selected_doctype = doctype;
		this.fieldselect.selected_fieldname = fieldname;
		this.toggle_controls(true);

		if (
			this.filters_config &&
			this.filters_config[condition] &&
			this.filters_config[condition].valid_for_fieldtypes.includes(df.fieldtype)
		) {
			let args = {};
			if (this.filters_config[condition].depends_on) {
				const field_name = this.filters_config[condition].depends_on;
				const filter_value = this.filter_list.get_filter_value(field_name);
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
		this.set_special_condition_labels(df.original_type);
		this.toggle_nested_set_conditions(df);
		// relabel: Date relabels the comparisons once the fieldtype is known
		this.set_condition(this.get_condition());

		this.destroy_calendar();
		let field_area = this.filter_edit_area.find(".filter-field").empty().get(0);
		df.placeholder = df.dynamic_link_hint || this.get_placeholder(df, this.get_condition());
		// starts blank, so picking a Select field doesn't filter by its first option
		if (df.fieldtype === "Select" && this.get_condition() !== "is") {
			if (Array.isArray(df.options)) {
				df.options = [{ label: "", value: "" }, ...df.options];
			} else if (!(df.options || "").startsWith("\n")) {
				df.options = "\n" + (df.options || "");
			}
		}
		if (df.fieldtype === "MultiSelectList") {
			df.get_data = (txt) => this.get_link_options(df, txt);
			df.change = () => this.on_change();
		}
		let f = frappe.ui.form.make_control({
			df: df,
			parent: field_area,
			only_input: true,
		});
		f.refresh();

		this.field = f;
		// a Dynamic Link swaps text box and Link picker as its Type comes and goes; keep the value
		if (old_text && (f.fieldtype === old_fieldtype || df.original_type === "Dynamic Link")) {
			this.field.set_value(old_text);
		}

		if (Array.isArray(old_text) && df.fieldtype !== old_fieldtype) {
			this.field.set_value(this.value);
		}

		this.bind_filter_field_events();
	}

	get_placeholder(df, condition) {
		const numeric = ["Int", "Float", "Currency", "Percent", "Rating"].includes(
			df.original_type
		);
		if (["in", "not in"].includes(condition) && df.fieldtype === "Data") {
			return numeric ? "100, 200, 300" : __("Values, comma separated");
		}
		if (["like", "not like"].includes(condition)) {
			return __("Text to match, % as wildcard");
		}
		if (condition === "is") return __("Select");
		if (condition === "Timespan") return __("Select period");
		if (df.fieldtype === "DateRange") return __("Select date range");
		if (["Date", "Datetime"].includes(df.fieldtype)) return __("Select date");
		if (df.fieldtype === "Time") return __("Select time");
		// named after the field, so an empty box says what goes in it
		const label = df.label ? __(df.label, null, df.parent) : "";
		const pick = ["Link", "Dynamic Link", "Select", "MultiSelect", "MultiSelectList"];
		if (pick.includes(df.fieldtype)) return label ? __("Select {0}", [label]) : __("Select");
		if (numeric || df.fieldtype === "Data")
			return label ? __("Enter {0}", [label]) : __("Value");
		return "";
	}

	get_link_options(df, txt) {
		return frappe
			.xcall("frappe.desk.search.search_link", {
				doctype: df.options,
				txt: txt || "",
				page_length: 20,
			})
			.then((r) =>
				(r?.results || r || []).map((d) => ({
					value: d.value,
					label: d.label || d.value,
					description: d.description || "",
				}))
			);
	}

	bind_filter_field_events() {
		if (!this.field.$input) return;

		// Apply filter on input focus out — but not when focus moves into the
		// combobox Link field's own panel (the pick is still in progress)
		this.field.$input.on("focusout", (e) => {
			if (e.relatedTarget && e.relatedTarget.closest(".es-combobox__panel")) return;
			// a combobox pick already applied this value
			if (this.field.combobox && this.field.get_value() === this.field.applied_value) return;
			this.on_change();
		});
		// a combobox pick or clear reaches the input as a change (Enter happens
		// in its panel, outside the wrapper)
		if (this.field.combobox) {
			this.field.$input.on("change", () => {
				if (this.field.get_value() === this.field.applied_value) return;
				this.field.applied_value = this.field.get_value();
				this.on_change();
			});
		} else {
			// a pick in a select or a datepicker lands as a change, with no focusout
			this.field.$input.on("change", () => this.on_change());
		}

		// run on enter
		$(this.field.wrapper)
			.find(":input")
			.keydown((e) => {
				if (e.which == 13 && this.field.df.fieldtype !== "MultiSelect") {
					this.on_change();
					this.on_enter && this.on_enter();
				}
			});
	}

	get_value() {
		return [
			this.fieldselect.selected_doctype,
			this.field.df.fieldname,
			this.get_condition(),
			this.get_selected_value(),
		];
	}

	get_selected_value() {
		return this.utils.get_selected_value(this.field, this.get_condition());
	}

	get_selected_label() {
		return this.utils.get_selected_label(this.field);
	}

	get_filter_group() {
		// `this.filter_list` is the FilterGroup in standalone use (dialogs, dashboards),
		// but the parent ListView in list views — drill through to the actual FilterGroup.
		return this.filter_list?.filter_area?.filter_list || this.filter_list;
	}

	resolve_dynamic_link(df, original_df) {
		if (df.original_type !== "Dynamic Link") return;

		if (!this.link_friendly_conditions.has(this.get_condition())) return;

		// get the filter whose value this Dynamic Link filter depends on, if any
		const peer = this.get_filter_group()?.get_filter?.(original_df.options);
		const peer_value = peer?.get_selected_value?.();

		if (peer && peer.get_condition() === "=" && peer_value) {
			df.fieldtype = "Link";
			df.options = peer_value;
			return;
		}

		// shown as the empty box's placeholder, so a filled value carries no hint
		const peer_label = this.get_dynamic_link_peer_label(original_df);
		df.dynamic_link_hint = __("Set {0} to search", [__(peer_label)]);
	}

	get_dynamic_link_peer_label(df) {
		const peer_df = frappe.meta.get_docfield(df.parent, df.options);
		return peer_df ? peer_df.label : df.options;
	}

	hide_invalid_conditions(fieldtype, original_type) {
		this.invalid_conditions =
			this.invalid_condition_map[original_type] ||
			this.invalid_condition_map[fieldtype] ||
			[];
	}

	set_special_condition_labels(original_type) {
		this.special_labels = this.special_condition_labels[original_type] || {};
	}

	toggle_nested_set_conditions(df) {
		this.show_nested_set =
			df.fieldtype === "Link" && frappe.boot.nested_set_doctypes.includes(df.options);
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

		let val = field.get_value() ?? field.value;

		if (!val && ["Link", "Dynamic Link"].includes(field.df.fieldtype)) {
			// HACK: link field with show title are async so their input value is "" but they have
			// some actual value set.
			val = field.value;
		}

		if (typeof val === "string") {
			val = strip(val);
		}

		if (condition == "is" && !val) {
			val = field.df.options[0].value;
		}

		// blank stays blank: nothing picked yet is not "No"
		if (field.df.original_type == "Check" && val) {
			val = val == "Yes" ? 1 : 0;
		}

		if (["like", "not like"].includes(condition)) {
			// automatically append wildcards
			if (val && !(val.startsWith("%") || val.endsWith("%"))) {
				val = "%" + val + "%";
			}
		} else if (["in", "not in"].includes(condition)) {
			if (Array.isArray(val)) {
				val = val.length ? val : null;
			} else if (val) {
				try {
					const parsed = JSON.parse(val);
					val = Array.isArray(parsed) ? parsed : [String(parsed)];
				} catch {
					val = val
						.split(",")
						.map((v) => strip(v))
						.filter((v) => v != null && v !== "");
				}
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
		if (["Link", "Dynamic Link"].includes(field.df.fieldtype)) {
			return field.get_label_value();
		}
	},

	get_default_condition(df) {
		const meta = frappe.get_meta(df.parent);
		if (["_assign", "_liked_by"].includes(df.fieldname)) {
			// stored as a JSON array, so an exact match can never hit
			return "like";
		} else if (df.fieldtype == "Data" && !meta?.is_large_table) {
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
		df.length = 1000; // this won't be saved, no need to apply 140 character limit here
		df.ignore_link_validation = true;

		// given
		if (fieldtype) {
			df.fieldtype = fieldtype;
			return;
		}

		// scrub
		if (["_assign", "_liked_by"].includes(df.fieldname)) {
			df.fieldtype = "Link";
			df.options = "User";
		} else if (df.fieldname == "docstatus") {
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
				"descendants of (inclusive)",
				"ancestors of",
				"not descendants of",
				"not ancestors of",
			].indexOf(condition) == -1
		) {
			df.fieldtype = "Data";
		}
		// options may be non-string, e.g. for Attach coerced to Data.
		if (
			df.fieldtype === "Data" &&
			typeof df.options === "string" &&
			df.options.toLowerCase() === "email"
		) {
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

	/**
	 * Generates timespan options for filter dropdown based on provided periods
	 * @param {Array<string>} periods - Array of period types to include
	 *     (e.g., "Last", "This", "Next", "Yesterday", "Today", "Tomorrow").
	 *     Additional custom values are allowed. The order of the periods is preserved.
	 * @returns {Array<{label: string, value: string}>} Array of option objects with label and value properties for the filter dropdown
	 */
	get_timespan_options(periods) {
		const last_options = [
			{
				label: __("Last 7 Days"),
				value: "last 7 days",
			},
			{
				label: __("Last 14 Days"),
				value: "last 14 days",
			},
			{
				label: __("Last 30 Days"),
				value: "last 30 days",
			},
			{
				label: __("Last 90 Days"),
				value: "last 90 days",
			},
			{
				label: __("Last Week"),
				value: "last week",
			},
			{
				label: __("Last Month"),
				value: "last month",
			},
			{
				label: __("Last Quarter"),
				value: "last quarter",
			},
			{
				label: __("Last 6 Months"),
				value: "last 6 months",
			},
			{
				label: __("Last Year"),
				value: "last year",
			},
		];
		const this_options = [
			{
				label: __("This Week"),
				value: "this week",
			},
			{
				label: __("This Month"),
				value: "this month",
			},
			{
				label: __("This Quarter"),
				value: "this quarter",
			},
			{
				label: __("This Year"),
				value: "this year",
			},
		];
		const next_options = [
			{
				label: __("Next 7 Days"),
				value: "next 7 days",
			},
			{
				label: __("Next 14 Days"),
				value: "next 14 days",
			},
			{
				label: __("Next 30 Days"),
				value: "next 30 days",
			},
			{
				label: __("Next Week"),
				value: "next week",
			},
			{
				label: __("Next Month"),
				value: "next month",
			},
			{
				label: __("Next Quarter"),
				value: "next quarter",
			},
			{
				label: __("Next 6 Months"),
				value: "next 6 months",
			},
			{
				label: __("Next Year"),
				value: "next year",
			},
		];

		const options = [];
		for (const period of periods) {
			switch (period) {
				case "Last":
					options.push(...last_options);
					break;
				case "This":
					options.push(...this_options);
					break;
				case "Next":
					options.push(...next_options);
					break;
				case "Yesterday":
					options.push({
						label: __("Yesterday"),
						value: "yesterday",
					});
					break;
				case "Today":
					options.push({
						label: __("Today"),
						value: "today",
					});
					break;
				case "Tomorrow":
					options.push({
						label: __("Tomorrow"),
						value: "tomorrow",
					});
					break;
				default:
					options.push({
						label: __(period),
						value: `${period.toLowerCase()}`,
					});
					break;
			}
		}

		return options;
	},
};
