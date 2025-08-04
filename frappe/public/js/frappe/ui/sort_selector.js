frappe.ui.SortSelector = class SortSelector {
	// parent:
	// change:
	// args:
	//		options: {fieldname:, label:}
	//		sort_by:
	//		sort_by_label:
	//		sort_order:
	//		doctype: (optional)
	constructor(opts) {
		$.extend(this, opts);
		this.labels = {};
		this.make();
	}
	make() {
		this.prepare_args();
		this.parent.find(".sort-selector").remove();
		this.wrapper = $(frappe.render_template("sort_selector", this.args)).appendTo(this.parent);
		this.bind_events();
	}
	bind_events() {
		var me = this;

		// order
		this.wrapper.find(".btn-order").on("click", function () {
			const order = $(this).attr("data-value") === "desc" ? "asc" : "desc";
			me.set_value(me.sort_by, order);
			(me.onchange || me.change)(me.sort_by, me.sort_order);
		});

		// select field
		this.wrapper.find(".dropdown-menu a.option").on("click", function () {
			me.set_value($(this).attr("data-value"), me.sort_order);
			(me.onchange || me.change)(me.sort_by, me.sort_order);
		});
	}
	set_value(sort_by, sort_order) {
		const $btn = this.wrapper.find(".btn-order");
		const $icon = $btn.find(".sort-order");
		const $text = this.wrapper.find(".dropdown-text");

		if (this.sort_by !== sort_by) {
			this.sort_by = sort_by;
			$text.html(__(this.get_label(sort_by)));
		}
		if (this.sort_order !== sort_order) {
			this.sort_order = sort_order;
			const title = sort_order === "desc" ? __("ascending") : __("descending");
			const icon_name = sort_order === "asc" ? "sort-ascending" : "sort-descending";
			$btn.attr("data-value", sort_order);
			$btn.attr("title", title);
			$icon.html(frappe.utils.icon(icon_name, "sm"));
		}
	}
	prepare_args() {
		var me = this;
		if (!this.args) {
			this.args = {};
		}

		// args as string
		if (this.args && typeof this.args === "string") {
			var order_by = this.args;
			this.args = {};

			if (order_by.includes("`.`")) {
				// scrub table name (separated by dot), like `tabTime Log`.`creation` desc`
				order_by = order_by.split(".")[1];
			}

			var parts = order_by.split(" ");
			if (parts.length === 2) {
				var fieldname = strip(parts[0], "`");

				this.args.sort_by = fieldname;
				this.args.sort_order = parts[1];
			}
		}

		if (this.args.options) {
			this.args.options.forEach(function (o) {
				me.labels[o.fieldname] = o.label;
			});
		}

		this.setup_from_doctype();

		// if label is missing, add from options
		if (this.args.sort_by && !this.args.sort_by_label) {
			this.args.options.every(function (o) {
				if (o.fieldname === me.args.sort_by) {
					me.args.sort_by_label = o.label;
					return false;
				}
				return true;
			});
		}
	}
	setup_from_doctype() {
		var me = this;
		var meta = frappe.get_meta(this.doctype);
		if (!meta) return;

		var { meta_sort_field, meta_sort_order } = this.get_meta_sort_field();

		if (!this.args.sort_by) {
			if (meta_sort_field) {
				this.args.sort_by = meta_sort_field;
				this.args.sort_order = meta_sort_order;
			} else {
				// default
				this.args.sort_by = "creation";
				this.args.sort_order = "desc";
			}
		}

		if (!this.args.sort_by_label) {
			this.args.sort_by_label = this.get_label(this.args.sort_by);
		}

		if (!this.args.options) {
			// default options
			var _options = [
				{ fieldname: "modified" },
				{ fieldname: "name" },
				{ fieldname: "creation" },
				{ fieldname: "idx" },
			];

			// title field
			if (meta.title_field) {
				_options.splice(1, 0, { fieldname: meta.title_field });
			}

			// sort field - set via DocType schema or Customize Form
			if (meta_sort_field) {
				_options.splice(1, 0, { fieldname: meta_sort_field });
			}

			// bold, mandatory and fields that are available in list view
			meta.fields.forEach(function (df) {
				if (
					(df.mandatory || df.bold || df.in_list_view || df.reqd) &&
					frappe.model.is_value_type(df.fieldtype) &&
					frappe.perm.has_perm(me.doctype, df.permlevel, "read")
				) {
					_options.push({ fieldname: df.fieldname, label: df.label });
				}
			});

			// add missing labels
			_options.forEach((option) => {
				if (!option.label) {
					option.label = me.get_label(option.fieldname);
				}
			});

			// de-duplicate
			this.args.options = _options.uniqBy((obj) => {
				return obj.fieldname;
			});
		}

		// set default
		this.sort_by = this.args.sort_by;
		this.sort_order = this.args.sort_order = this.args.sort_order.toLowerCase();
	}
	get_meta_sort_field() {
		var meta = frappe.get_meta(this.doctype);

		if (!meta) {
			return {
				meta_sort_field: null,
				meta_sort_order: null,
			};
		}

		if (meta.sort_field) {
			var parts = meta.sort_field.split(",")[0].split(" ");
			return {
				meta_sort_field: parts[0],
				meta_sort_order: meta.sort_order ? meta.sort_order.toLowerCase() : "",
			};
		} else {
			return {
				meta_sort_field: meta.sort_field || "creation",
				meta_sort_order: meta.sort_order ? meta.sort_order.toLowerCase() : "",
			};
		}
	}
	get_label(fieldname) {
		if (fieldname === "idx") {
			return __("Most Used");
		} else {
			return this.labels[fieldname] || frappe.meta.get_label(this.doctype, fieldname);
		}
	}
	get_sql_string() {
		// build string like: `tabSales Invoice`.subject, `tabSales Invoice`.name desc
		const table_name = "`tab" + this.doctype + "`";
		const sort_by = `${table_name}.${this.sort_by}`;
		if (!["name", "creation", "modified"].includes(this.sort_by)) {
			// add name column for deterministic ordering
			return `${sort_by} ${this.sort_order}, ${table_name}.name ${this.sort_order}`;
		} else {
			return `${sort_by} ${this.sort_order}`;
		}
	}
};
