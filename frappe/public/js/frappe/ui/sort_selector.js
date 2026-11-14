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
		this.wrapper = $('<div class="sort-selector flex items-center"></div>').appendTo(
			this.parent
		);

		const { title, icon } = this.get_order(this.sort_order);
		this.$order_button = frappe.ui.button({
			icon,
			title,
			css_class: "btn-order rounded-se-none rounded-ee-none",
			attrs: { "data-value": this.sort_order },
			onclick: () => this.select(this.sort_by, this.sort_order === "desc" ? "asc" : "desc"),
		});
		this.$field_button = frappe.ui.dropdown({
			button: {
				label: __(this.args.sort_by_label, null, this.doctype),
				icon_right: "chevron-down",
				css_class: "sort-selector-button border-s rounded-ss-none rounded-es-none",
			},
			align: "end",
			options: () =>
				this.args.options.map(({ fieldname, label }) => ({
					label: __(label, null, this.doctype),
					selected: fieldname === this.sort_by,
					onclick: () => this.select(fieldname, this.sort_order),
				})),
		});
		$('<div class="sort-selector-group flex items-center hidden-xs"></div>')
			.append(this.$order_button, this.$field_button)
			.appendTo(this.wrapper);

		this.$sheet_button = frappe.ui.button({
			icon,
			title: __("Sort"),
			css_class: "hidden-lg ms-1",
			onclick: () => this.open_sheet(),
		});
		this.wrapper.append(this.$sheet_button);
	}
	select(sort_by, sort_order) {
		this.set_value(sort_by, sort_order);
		(this.onchange || this.change)(this.sort_by, this.sort_order);
	}
	async open_sheet() {
		// a second tap while the sheet's bundle loads opens nothing
		if (this.opening_sheet) return;
		this.opening_sheet = true;
		await frappe
			.require(["bottom_sheet.bundle.js", "bottom_sheet.bundle.css"])
			.finally(() => (this.opening_sheet = false));
		const select = (sort_by, sort_order) => {
			if (sort_by === this.sort_by && sort_order === this.sort_order) return;
			this.select(sort_by, sort_order);
		};
		new frappe.ui.BottomSheet({
			title: __("Sort by"),
			options: [
				...["desc", "asc"].map((order) => ({
					label: this.get_order(order).label,
					icon: this.get_order(order).icon,
					selected: order === this.sort_order,
					onclick: () => select(this.sort_by, order),
				})),
				{
					group: __("Field"),
					hide_label: true,
					options: this.args.options.map(({ fieldname, label }) => ({
						label: __(label, null, this.doctype),
						selected: fieldname === this.sort_by,
						onclick: () => select(fieldname, this.sort_order),
					})),
				},
			],
		}).open();
	}
	set_value(sort_by, sort_order) {
		if (this.sort_by !== sort_by) {
			this.sort_by = sort_by;
			this.$field_button
				.find(".es-button__label")
				.text(__(this.get_label(sort_by), null, this.doctype));
		}
		if (this.sort_order !== sort_order) {
			this.sort_order = sort_order;
			const { title, icon } = this.get_order(sort_order);
			this.$order_button.attr({ "data-value": sort_order, title, "aria-label": title });
			frappe.ui.button.dress(this.$order_button, { icon });
			frappe.ui.button.dress(this.$sheet_button, { icon });
		}
	}
	get_order(sort_order) {
		return sort_order === "asc"
			? { label: __("Ascending"), title: __("ascending"), icon: "arrow-up-narrow-wide" }
			: { label: __("Descending"), title: __("descending"), icon: "arrow-down-wide-narrow" };
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

			if (order_by.includes(",")) {
				// only keep first
				order_by = order_by.split(",")[0];
			}

			if (order_by.includes("`.")) {
				// scrub table name (separated by dot), like "`tabTime Log`.`creation` desc"
				// and is robust to missing backticks
				order_by = order_by.split(".")[1].replace("`", "");
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
		this.sort_by = this.args.sort_by;
		this.sort_order = this.args.sort_order = this.args.sort_order?.toLowerCase();

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
		// build string like: `tabSales Invoice`.`subject`, `tabSales Invoice`.`name` desc
		const table_name = "`tab" + this.doctype + "`";
		const sort_by = `${table_name}.\`${this.sort_by}\``;
		if (!["name", "creation", "modified"].includes(this.sort_by)) {
			// add name column for deterministic ordering
			return `${sort_by} ${this.sort_order}, ${table_name}.\`name\` ${this.sort_order}`;
		} else {
			return `${sort_by} ${this.sort_order}`;
		}
	}
};
