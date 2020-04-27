class WidgetDialog {
	constructor(opts) {
		Object.assign(this, opts);
		this.editing = Boolean(this.values && Object.keys(this.values).length);
	}

	make() {
		this.make_dialog();
		this.setup_dialog_events();
		this.dialog.show();

		this.editing && this.set_default_values();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: this.get_title(),
			fields: this.get_fields(),
			primary_action: (data) => {
				data = this.process_data(data);

				if (!this.editing) {
					data.name = `${this.type}-${this.label}-${frappe.utils.get_random(20)}`;
				}

				this.dialog.hide();
				this.primary_action(data);
			},
			primary_action_label: this.primary_action_label || __("Add"),
		});
	}

	get_title() {
		// DO NOT REMOVE: Comment to load translation
		// __("New Chart") __("New Shortcut") __("Edit Chart") __("Edit Shortcut")

		let action = this.editing ? "Edit" : "Add";
		return __(`${action} ${frappe.utils.to_title_case(this.type)}`);
	}

	get_fields() {
		//
	}

	set_default_values() {
		return this.dialog.set_values(this.values);
	}

	process_data(data) {
		return data;
	}

	setup_dialog_events() {
		//
	}

	hide_field(fieldname) {
		this.dialog.set_df_property(fieldname, "hidden", true);
	}

	show_field(fieldname) {
		this.dialog.set_df_property(fieldname, "hidden", false);
	}
}

class ChartDialog extends WidgetDialog {
	constructor(opts) {
		super(opts);
	}

	get_fields() {
		return [
			{
				fieldtype: "Link",
				fieldname: "chart_name",
				label: "Chart Name",
				options: "Dashboard Chart",
				reqd: 1,
			},
			{
				fieldtype: "Data",
				fieldname: "label",
				label: "Label",
			},
		];
	}

	process_data(data) {
		data.label = data.label ? data.label : data.chart_name;
		return data;
	}
}

class ShortcutDialog extends WidgetDialog {
	constructor(opts) {
		super(opts);
	}

	hide_filters() {
		this.hide_field("count_section_break");
		this.hide_field("filters_section_break");
	}

	show_filters() {
		this.show_field("count_section_break");
		this.show_field("filters_section_break");
	}

	get_fields() {
		return [
			{
				fieldtype: "Select",
				fieldname: "type",
				label: "Type",
				reqd: 1,
				options: "DocType\nReport\nPage",
				onchange: () => {
					if (this.dialog.get_value("type") == "DocType") {
						this.dialog.fields_dict.link_to.get_query = () => {
							return { filters: { istable: false } };
						};
					} else {
						this.dialog.fields_dict.link_to.get_query = null;
					}
				},
			},
			{
				fieldtype: "Data",
				fieldname: "label",
				label: "Label",
			},
			{
				fieldtype: "Column Break",
				fieldname: "column_break_4",
			},
			{
				fieldtype: "Dynamic Link",
				fieldname: "link_to",
				label: "Link To",
				reqd: 1,
				options: "type",
				onchange: () => {
					if (this.dialog.get_value("type") == "DocType") {
						let doctype = this.dialog.get_value("link_to");

						doctype &&
							frappe.db
								.get_value("DocType", doctype, "issingle")
								.then((res) => {
									if (res.message && res.message.issingle) {
										this.hide_filters();
									} else {
										this.setup_filter(doctype);
										this.show_filters();
									}
								});
					} else {
						this.hide_filters();
					}
				},
			},
			{
				fieldtype: "Section Break",
				fieldname: "filters_section_break",
				label: "Count Filter",
				hidden: 1,
			},
			{
				fieldtype: "HTML",
				fieldname: "filter_area_loading",
			},
			{
				fieldtype: "HTML",
				fieldname: "filter_area",
				hidden: 1,
			},
			{
				fieldtype: "Section Break",
				fieldname: "count_section_break",
				label: "Count Customizations",
				hidden: 1,
			},
			{
				fieldtype: "Color",
				fieldname: "color",
				label: "Color",
			},
			{
				fieldtype: "Column Break",
				fieldname: "column_break_3",
			},
			{
				fieldtype: "Data",
				fieldname: "format",
				label: "Format",
				description: "For Example: {} Open",
			},
		];
	}

	set_default_values() {
		super.set_default_values().then(() => {
			this.dialog.fields_dict.link_to.df.onchange();
		});
	}

	process_data(data) {
		let stats_filter = {};

		if (this.dialog.get_value("type") == "DocType" && this.filter_group) {
			let filters = this.filter_group.get_filters();
			filters.forEach((arr) => {
				stats_filter[arr[1]] = [arr[2], arr[3]];
			});

			data.stats_filter = JSON.stringify(stats_filter);
		}

		data.label = data.label
			? data.label
			: frappe.model.unscrub(data.link_to);

		return data;
	}

	setup_filter(doctype) {
		if (this.filter_group) {
			this.filter_group.wrapper.empty();
			delete this.filter_group;
		}

		let $loading = this.dialog.get_field("filter_area_loading").$wrapper;
		$(`<span class="text-muted">Loading Filters...</span>`).appendTo($loading);

		this.filters = [];

		if (this.values && this.values.stats_filter) {
			const filters_json = JSON.parse(this.values.stats_filter);
			this.filters = Object.keys(filters_json).map((filter) => {
				let val = filters_json[filter];
				return [this.values.link_to, filter, val[0], val[1], false];
			});
		}

		this.filter_group = new frappe.ui.FilterGroup({
			parent: this.dialog.get_field("filter_area").$wrapper,
			doctype: doctype,
			on_change: () => {},
		});

		frappe.model.with_doctype(doctype, () => {
			this.filter_group.add_filters_to_filter_group(this.filters);
			this.hide_field("filter_area_loading");
			this.show_field("filter_area");
		});
	}
}

export default function get_dialog_constructor(type) {
	const widget_map = {
		chart: ChartDialog,
		shortcut: ShortcutDialog,
	};

	return widget_map[type] || WidgetDialog;
}
