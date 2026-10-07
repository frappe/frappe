// Searchable field picker for filters: a combobox over the doctype's own and
// standard fields, with each child table's fields in a group of their own.
frappe.ui.FieldSelect = class FieldSelect {
	// opts parent, doctype, parent_doctype, filter_fields, with_blank, select, placeholder
	constructor(opts) {
		$.extend(this, opts);
		this.fields_by_name = {};
		this.options = [];

		if (this.filter_fields) {
			for (const df of this.filter_fields) this.add_field_option(df);
		} else {
			this.build_options();
		}

		this.combobox = new frappe.ui.Combobox({
			placeholder: this.placeholder || __("Select field"),
			search_placeholder: __("Search fields..."),
			clear_button: false,
			hide_search: this.options.length <= 8,
			// narrowed here, by label and fieldname: every value starts with the
			// doctype, so the doctype's own name would match all of them
			options: (query) => this.get_combobox_options(query),
			on_change: (value) => this.on_pick(value),
		});
		// the trigger keeps the old `$input` name: callers focus it
		this.$input = this.combobox.$trigger.appendTo(this.parent);
		this.input_class && this.$input.addClass(this.input_class);
	}

	on_pick(value) {
		const item = this.options.find((o) => o.value === value);
		if (!item) return;
		this.selected_doctype = item.doctype;
		this.selected_fieldname = item.fieldname;
		this.select && this.select(item.doctype, item.fieldname);
	}

	// loose rows first (the doctype's own fields), then one group per child table
	get_combobox_options(query = "") {
		const q = query.trim().toLowerCase();
		// a table's name finds its fields too
		const shown = this.options.filter(
			(o) =>
				!q || `${o.label} ${o.fieldname || ""} ${o.group || ""}`.toLowerCase().includes(q)
		);
		const main = shown.filter((o) => !o.group);
		const groups = [...new Set(shown.filter((o) => o.group).map((o) => o.group))];
		return [
			...main,
			...groups.map((group) => ({
				group,
				options: shown.filter((o) => o.group === group),
			})),
		];
	}

	get_value() {
		return this.selected_doctype
			? this.selected_doctype + "." + this.selected_fieldname
			: null;
	}

	val(value) {
		if (value === undefined) {
			return this.get_value();
		} else {
			this.set_value(value);
		}
	}

	clear() {
		this.selected_doctype = null;
		this.selected_fieldname = null;
		this.combobox.set_value(null);
	}

	set_value(doctype, fieldname) {
		this.clear();
		if (!doctype) return;

		// old style
		if (doctype.indexOf(".") !== -1) {
			const parts = doctype.split(".");
			doctype = parts[0];
			fieldname = parts[1];
		}

		const item = this.options.find((o) => o.doctype === doctype && o.fieldname === fieldname);
		if (!item) return;
		this.selected_doctype = doctype;
		this.selected_fieldname = fieldname;
		this.combobox.set_value(item.value, { label: item.label });
	}

	focus() {
		this.combobox.focus();
	}

	open() {
		this.combobox.open({ motion: "instant" });
	}

	build_options() {
		const me = this;
		me.table_fields = [];
		let std_filters = $.map(frappe.model.std_fields, function (d) {
			const opts = { parent: me.doctype };
			if (d.fieldname == "name") opts.options = me.doctype;
			return $.extend(copy_dict(d), opts);
		});

		// add parenttype column
		const doctype_obj = frappe.get_meta(me.doctype);
		if (doctype_obj && cint(doctype_obj.istable)) {
			std_filters = std_filters.concat([
				{
					fieldname: "parent",
					fieldtype: "Data",
					label: "Parent",
					parent: me.doctype,
				},
			]);
		}

		// blank
		if (this.with_blank) {
			this.options.push({
				label: "",
				value: "",
			});
		}

		// main table, ID first
		const main_table_fields = std_filters.concat(frappe.meta.docfield_list[me.doctype]);
		const sorted = frappe.utils.sort(main_table_fields, "label", "string");
		const id_index = sorted.findIndex((df) => df.fieldname == "name");
		if (id_index > 0) sorted.unshift(...sorted.splice(id_index, 1));
		$.each(sorted, function (i, df) {
			if (df.is_virtual) {
				return;
			}

			const doctype =
				frappe.get_meta(me.doctype).istable && me.parent_doctype
					? me.parent_doctype
					: me.doctype;

			// show fields where user has read access and if report hide flag is not set
			if (frappe.perm.has_perm(doctype, df.permlevel, "read")) me.add_field_option(df);
		});

		// child tables
		$.each(me.table_fields, function (i, table_df) {
			if (table_df.options && !table_df.is_virtual) {
				let child_table_fields = [].concat(frappe.meta.docfield_list[table_df.options]);

				if (table_df.fieldtype === "Table MultiSelect") {
					const link_field = frappe.meta
						.get_docfields(table_df.options)
						.find((df) => df.fieldtype === "Link");
					child_table_fields = link_field ? [link_field] : [];
				}

				$.each(frappe.utils.sort(child_table_fields, "label", "string"), function (i, df) {
					const doctype =
						frappe.get_meta(me.doctype).istable && me.parent_doctype
							? me.parent_doctype
							: me.doctype;

					// show fields where user has read access and if report hide flag is not set
					if (frappe.perm.has_perm(doctype, df.permlevel, "read"))
						me.add_field_option(df, table_df);
				});
			}
		});
	}

	add_field_option(df, table_df) {
		const me = this;

		if (df.fieldname == "docstatus" && !frappe.model.is_submittable(me.doctype)) return;

		if (frappe.model.table_fields.includes(df.fieldtype)) {
			me.table_fields.push(df);
			return;
		}

		let label = null;
		let table = null;
		let group = null;

		if (me.doctype && df.parent == me.doctype) {
			label = __(df.label, null, df.parent);
			table = me.doctype;
		} else if (table_df) {
			// a child table's field: grouped under the table's label
			label = __(df.label, null, df.parent);
			table = df.parent;
			group = table_df.label ? __(table_df.label) : __(df.parent);
		} else {
			label = __(df.label, null, df.parent) + " (" + __(df.parent) + ")";
			table = df.parent;
		}

		if (
			frappe.model.no_value_type.indexOf(df.fieldtype) == -1 &&
			!(me.fields_by_name[df.parent] && me.fields_by_name[df.parent][df.fieldname])
		) {
			this.options.push({
				label: label,
				value: table + "." + df.fieldname,
				fieldname: df.fieldname,
				doctype: df.parent,
				group: group,
			});
			if (!me.fields_by_name[df.parent]) me.fields_by_name[df.parent] = {};
			me.fields_by_name[df.parent][df.fieldname] = df;
		}
	}
};
