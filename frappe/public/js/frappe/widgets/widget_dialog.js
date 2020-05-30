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

				if (!this.editing && !data.name) {
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
		return __(`${action} ${frappe.model.unscrub(this.type)}`);
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
				options: "DocType\nReport\nPage\nDashboard",
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

			if (filters.length) {
				filters.forEach((arr) => {
					stats_filter[arr[1]] = [arr[2], arr[3]];
				});

				data.stats_filter = JSON.stringify(stats_filter);
			}
		}

		data.label = data.label
			? data.label
			: frappe.model.unscrub(data.link_to);

		return data;
	}
}

class NumberCardDialog extends WidgetDialog {
	constructor(opts) {
		super(opts);
	}

	get_fields() {
		let fields;
		fields = [
			{
				fieldtype: 'Select',
				label: 'Choose Existing Card or create New Card',
				fieldname: 'new_or_existing',
				options: ['New Card', 'Existing Card']
			},
			{
				fieldtype: 'Link',
				fieldname: 'card',
				label: 'Number Cards',
				options: 'Number Card',
				get_query: () => {
					return {
						'query': 'frappe.desk.doctype.number_card.number_card.get_cards_for_user',
						filters: {
							document_type: this.document_type,
						}
					};
				},
				depends_on: 'eval: doc.new_or_existing == "Existing Card"'
			},
			{
				fieldtype: 'Section Break',
				fieldname: 'sb_1',
				depends_on: 'eval: doc.new_or_existing == "New Card"'
			},
			{
				label: 'Label',
				fieldname: 'label',
				fieldtype: 'Data',
				mandatory_depends_on: 'eval: doc.new_or_existing == "New Card"'
			},
			{
				label: 'Doctype',
				fieldname: 'document_type',
				fieldtype: 'Link',
				options: 'DocType',
				onchange: () => {
					this.document_type = this.dialog.get_value("document_type");
					this.set_aggregate_function_fields(this.dialog.get_values());
					this.setup_filter(this.document_type);
				},
				hidden: 1
			},
			{
				label: 'Color',
				fieldname: 'color',
				fieldtype: 'Color'
			},
			{
				fieldtype: "Column Break",
				fieldname: "cb_1",
			},
			{
				label: 'Function',
				fieldname: 'function',
				fieldtype: 'Select',
				options: ['Count', 'Sum', 'Average', 'Minimum', 'Maximum'],
				mandatory_depends_on: 'eval: doc.new_or_existing == "New Card"'
			},
			{
				label: 'Function Based On',
				fieldname: 'aggregate_function_based_on',
				fieldtype: 'Select',
				depends_on: "eval: doc.function !== 'Count'",
				mandatory_depends_on: 'eval: doc.function !== "Count" && doc.new_or_existing == "New Card"'
			},
			{
				fieldtype: "Section Break",
				fieldname: "sb_1",
				label: 'Add Filters',
				depends_on: 'eval: doc.new_or_existing == "New Card"'
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
				fieldname: "sb_1",
			},
		];

		return fields;
	}

	setup_dialog_events() {
		if (!this.document_type) {
			if (this.default_values['doctype']) {
				this.document_type = this.default_values['doctype'];
				this.setup_filter(this.default_values['doctype']);
				this.set_aggregate_function_fields();
			} else {
				this.show_field('document_type');
			}
		}
	}

	set_aggregate_function_fields() {
		let aggregate_function_fields = [];
		if (this.document_type) {
			frappe.get_meta(this.document_type).fields.map(df => {
				if (frappe.model.numeric_fieldtypes.includes(df.fieldtype)) {
					if (df.fieldtype == 'Currency') {
						if (!df.options || df.options !== 'Company:company:default_currency') {
							return;
						}
					}
					aggregate_function_fields.push({label: df.label, value: df.fieldname});
				}
			});
		}
		this.dialog.set_df_property('aggregate_function_based_on', 'options', aggregate_function_fields);
	}

	process_data(data) {
		if (data.new_or_existing == 'Existing Card') {
			data.name = data.card;
		}
		data.stats_filter = JSON.stringify(this.filter_group.get_filters());
		data.document_type = this.document_type;

		return data;
	}
}

export default function get_dialog_constructor(type) {
	const widget_map = {
		chart: ChartDialog,
		shortcut: ShortcutDialog,
		number_card: NumberCardDialog,
	};

	return widget_map[type] || WidgetDialog;
}
