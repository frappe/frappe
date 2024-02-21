frappe.provide("frappe.views");

frappe.views.DashboardView = class DashboardView extends frappe.views.ListView {
	get view_name() {
		return "Dashboard";
	}

	setup_defaults() {
		return super.setup_defaults().then(() => {
			this.page_title = __("{0} Dashboard", [__(this.doctype)]);
			this.dashboard_settings =
				frappe.get_user_settings(this.doctype)["dashboard_settings"] || null;
		});
	}

	render() {}

	setup_page() {
		this.hide_sidebar = true;
		this.hide_page_form = true;
		this.hide_filters = true;
		this.hide_sort_selector = true;
		super.setup_page();
	}

	setup_view() {
		if (this.chart_group || this.number_card_group) {
			return;
		}

		this.setup_dashboard_page();
		this.setup_dashboard_customization();
		this.make_dashboard();
	}

	setup_dashboard_customization() {
		this.page.add_menu_item(__("Customize Dashboard"), () => this.customize());
		this.page.add_menu_item(__("Reset Dashboard Customizations"), () =>
			this.reset_dashboard_customization()
		);
		this.add_customization_buttons();
	}

	setup_dashboard_page() {
		const chart_wrapper_html = `<div class="dashboard-view"></div>`;

		this.$frappe_list.html(chart_wrapper_html);
		this.page.clear_secondary_action();
		this.$dashboard_page = this.$page
			.find(".layout-main-section-wrapper")
			.addClass("dashboard-page");
		this.page.main.removeClass("frappe-card");

		this.$dashboard_wrapper = this.$page.find(".dashboard-view");
		this.$chart_header = this.$page.find(".dashboard-header");

		frappe.utils.bind_actions_with_object(this.$dashboard_page, this);
	}

	add_customization_buttons() {
		this.save_customizations_button = this.page.add_button(
			__("Save Customizations"),
			() => {
				this.save_dashboard_customization();
				this.page.standard_actions.show();
			},
			{ btn_class: "btn-primary" }
		);

		this.discard_customizations_button = this.page.add_button(__("Discard"), () => {
			this.discard_dashboard_customization();
			this.page.standard_actions.show();
		});

		this.toggle_customization_buttons(false);
	}

	set_primary_action() {
		// Don't render Add doc button for dashboard view
	}

	toggle_customization_buttons(show) {
		this.save_customizations_button.toggle(show);
		this.discard_customizations_button.toggle(show);
	}

	make_dashboard() {
		if (this.dashboard_settings) {
			this.charts = this.dashboard_settings.charts;
			this.number_cards = this.dashboard_settings.number_cards;
			this.render_dashboard();
		} else {
			frappe.run_serially([
				() =>
					this.fetch_dashboard_items(
						"Dashboard Chart",
						{
							chart_type: ["in", ["Count", "Sum", "Group By"]],
							document_type: this.doctype,
							is_public: 1,
						},
						"charts"
					),
				() =>
					this.fetch_dashboard_items(
						"Number Card",
						{
							document_type: this.doctype,
							is_public: 1,
						},
						"number_cards"
					),
				() => this.render_dashboard(),
			]);
		}
	}

	render_dashboard() {
		this.$dashboard_wrapper.empty();

		frappe.dashboard_utils.get_dashboard_settings().then((settings) => {
			this.dashboard_chart_settings = settings.chart_config
				? JSON.parse(settings.chart_config)
				: {};
			this.charts.map((chart) => {
				chart.label = chart.chart_name;
				chart.chart_settings = this.dashboard_chart_settings[chart.chart_name] || {};
			});
			this.render_dashboard_charts();
		});
		this.render_number_cards();

		if (!this.charts.length && !this.number_cards.length) {
			this.render_empty_state();
		}
	}

	fetch_dashboard_items(doctype, filters, obj_name) {
		return frappe.db
			.get_list(doctype, {
				filters: filters,
				fields: ["*"],
			})
			.then((items) => {
				this[obj_name] = items;
			});
	}

	render_number_cards() {
		this.number_card_group = new frappe.widget.WidgetGroup({
			container: this.$dashboard_wrapper,
			type: "number_card",
			columns: 3,
			options: {
				allow_sorting: true,
				allow_create: true,
				allow_delete: true,
				allow_hiding: true,
			},
			default_values: { doctype: this.doctype },
			widgets: this.number_cards || [],
			in_customize_mode: this.in_customize_mode || false,
		});

		this.in_customize_mode && this.number_card_group.customize();
	}

	render_dashboard_charts() {
		this.chart_group = new frappe.widget.WidgetGroup({
			container: this.$dashboard_wrapper,
			type: "chart",
			columns: 2,
			height: 240,
			options: {
				allow_sorting: true,
				allow_create: true,
				allow_delete: true,
				allow_hiding: true,
				allow_resize: true,
			},
			custom_dialog: () => this.show_add_chart_dialog(),
			widgets: this.charts,
			in_customize_mode: this.in_customize_mode || false,
		});

		this.in_customize_mode && this.chart_group.customize();
		this.chart_group.container.find(".widget-group-head").hide();
	}

	render_empty_state() {
		const no_result_message_html = `<p>${__(
			"You haven't added any Dashboard Charts or Number Cards yet."
		)}
			<br>${__("Click On Customize to add your first widget")}</p>`;

		const customize_button = `<p><button class="btn btn-primary btn-sm" data-action="customize">
				${__("Customize")}
			</button></p>`;

		const empty_state_image = "/assets/frappe/images/ui-states/list-empty-state.svg";

		const empty_state_html = `<div class="msg-box no-border empty-dashboard">
			<div>
				<img src="${empty_state_image}" alt="Generic Empty State" class="null-state">
			</div>
			${no_result_message_html}
			${customize_button}
		</div>`;

		this.$dashboard_wrapper.append(empty_state_html);
		this.$empty_state = this.$dashboard_wrapper.find(".empty-dashboard");
	}

	customize() {
		if (this.in_customize_mode) {
			return;
		}

		this.page.standard_actions.hide();

		if (this.$empty_state) {
			this.$empty_state.remove();
		}

		this.toggle_customize(true);
		this.in_customize_mode = true;
		this.chart_group.customize();
		this.number_card_group.customize();
	}

	get_widgets_to_save(widget_group) {
		const config = widget_group.get_widget_config();
		let widgets = [];
		config.order.map((widget_name) => {
			widgets.push(config.widgets[widget_name]);
		});
		return this.remove_duplicates(widgets);
	}

	save_dashboard_customization() {
		this.toggle_customize(false);

		const charts = this.get_widgets_to_save(this.chart_group);
		const number_cards = this.get_widgets_to_save(this.number_card_group);

		this.dashboard_settings = {
			charts: charts,
			number_cards: number_cards,
		};

		frappe.model.user_settings.save(
			this.doctype,
			"dashboard_settings",
			this.dashboard_settings
		);
		this.make_dashboard();
	}

	discard_dashboard_customization() {
		this.dashboard_settings =
			frappe.get_user_settings(this.doctype)["dashboard_settings"] || null;
		this.toggle_customize(false);
		this.render_dashboard();
	}

	reset_dashboard_customization() {
		frappe.confirm(__("Are you sure you want to reset all customizations?"), () => {
			this.dashboard_settings = null;
			frappe.model.user_settings
				.save(this.doctype, "dashboard_settings", this.dashboard_settings)
				.then(() => this.make_dashboard());

			this.toggle_customize(false);
		});
	}

	toggle_customize(show) {
		this.toggle_customization_buttons(show);
		this.in_customize_mode = show;
	}

	show_add_chart_dialog() {
		let fields = this.get_field_options();
		const dialog = new frappe.ui.Dialog({
			title: __("Add a {0} Chart", [__(this.doctype)]),
			fields: [
				{
					fieldname: "new_or_existing",
					fieldtype: "Select",
					label: "Choose an existing chart or create a new chart",
					options: ["New Chart", "Existing Chart"],
					reqd: 1,
				},
				{
					label: "Chart",
					fieldname: "chart",
					fieldtype: "Link",
					get_query: () => {
						return {
							query: "frappe.desk.doctype.dashboard_chart.dashboard_chart.get_charts_for_user",
							filters: {
								document_type: this.doctype,
							},
						};
					},
					options: "Dashboard Chart",
					depends_on: 'eval: doc.new_or_existing == "Existing Chart"',
				},
				{
					fieldname: "sb_2",
					fieldtype: "Section Break",
					depends_on: 'eval: doc.new_or_existing == "New Chart"',
				},
				{
					label: "Chart Label",
					fieldname: "label",
					fieldtype: "Data",
					mandatory_depends_on: 'eval: doc.new_or_existing == "New Chart"',
				},
				{
					fieldname: "cb_1",
					fieldtype: "Column Break",
				},
				{
					label: "Chart Type",
					fieldname: "chart_type",
					fieldtype: "Select",
					options: ["Time Series", "Group By"],
					mandatory_depends_on: 'eval: doc.new_or_existing == "New Chart"',
				},
				{
					fieldname: "sb_2",
					fieldtype: "Section Break",
					label: "Chart Config",
					depends_on:
						'eval: doc.chart_type == "Time Series" && doc.new_or_existing == "New Chart"',
				},
				{
					label: "Function",
					fieldname: "chart_function",
					fieldtype: "Select",
					options: ["Count", "Sum", "Average"],
					default: "Count",
				},
				{
					label: "Timespan",
					fieldtype: "Select",
					fieldname: "timespan",
					depends_on: 'eval: doc.chart_type == "Time Series"',
					options: ["Last Year", "Last Quarter", "Last Month", "Last Week"],
					default: "Last Year",
				},
				{
					fieldname: "cb_2",
					fieldtype: "Column Break",
				},
				{
					label: "Value Based On",
					fieldtype: "Select",
					fieldname: "based_on",
					options: fields.value_fields,
					depends_on: 'eval: doc.chart_function=="Sum"',
				},
				{
					label: "Time Series Based On",
					fieldtype: "Select",
					fieldname: "based_on",
					options: fields.date_fields,
					mandatory_depends_on: 'eval: doc.chart_type == "Time Series"',
				},
				{
					label: "Time Interval",
					fieldname: "time_interval",
					fieldtype: "Select",
					depends_on: 'eval: doc.chart_type == "Time Series"',
					options: ["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"],
					default: "Monthly",
				},
				{
					fieldname: "sb_2",
					fieldtype: "Section Break",
					label: "Chart Config",
					depends_on:
						'eval: doc.chart_type == "Group By" && doc.new_or_existing == "New Chart"',
				},
				{
					label: "Group By Type",
					fieldname: "group_by_type",
					fieldtype: "Select",
					options: ["Count", "Sum", "Average"],
					default: "Count",
				},
				{
					label: "Aggregate Function Based On",
					fieldtype: "Select",
					fieldname: "aggregate_function_based_on",
					options: fields.aggregate_function_fields,
					depends_on: 'eval: ["Sum", "Average"].includes(doc.group_by_type)',
				},
				{
					fieldname: "cb_2",
					fieldtype: "Column Break",
				},
				{
					label: "Group By Based On",
					fieldtype: "Select",
					fieldname: "group_by_based_on",
					options: fields.group_by_fields,
					default: "Last Year",
				},
				{
					label: "Number of Groups",
					fieldtype: "Int",
					fieldname: "number_of_groups",
					default: 0,
				},
				{
					fieldname: "sb_3",
					fieldtype: "Section Break",
					depends_on: 'eval: doc.new_or_existing == "New Chart"',
				},
				{
					label: "Chart Type",
					fieldname: "type",
					fieldtype: "Select",
					options: ["Line", "Bar", "Percentage", "Pie"],
					depends_on: 'eval: doc.new_or_existing == "New Chart"',
				},
				{
					fieldname: "cb_1",
					fieldtype: "Column Break",
				},
				{
					label: "Chart Color",
					fieldname: "color",
					fieldtype: "Color",
					depends_on: 'eval: doc.new_or_existing == "New Chart"',
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				let chart = values;
				if (chart.new_or_existing == "New Chart") {
					chart.chart_name = chart.label;
					chart.chart_type =
						chart.chart_type == "Time Series"
							? chart.chart_function
							: chart.chart_type;
					chart.document_type = this.doctype;
					chart.filters_json = "[]";
					frappe
						.xcall(
							"frappe.desk.doctype.dashboard_chart.dashboard_chart.create_dashboard_chart",
							{ args: chart }
						)
						.then((doc) => {
							this.chart_group.new_widget.on_create({
								chart_name: doc.chart_name,
								name: doc.chart_name,
								label: chart.label,
							});
						});
				} else {
					this.chart_group.new_widget.on_create({
						chart_name: chart.chart,
						label: chart.chart,
						name: chart.chart,
					});
				}
				dialog.hide();
			},
		});
		dialog.show();
	}

	get_field_options() {
		let date_fields = [
			{ label: __("Created On"), value: "creation" },
			{ label: __("Last Modified On"), value: "modified" },
		];
		let value_fields = [];
		let group_by_fields = [];
		let aggregate_function_fields = [];

		frappe.get_meta(this.doctype).fields.map((df) => {
			if (["Date", "Datetime"].includes(df.fieldtype)) {
				date_fields.push({ label: df.label, value: df.fieldname });
			}
			if (frappe.model.numeric_fieldtypes.includes(df.fieldtype)) {
				if (df.fieldtype == "Currency") {
					if (!df.options || df.options !== "Company:company:default_currency") {
						return;
					}
				}
				value_fields.push({ label: df.label, value: df.fieldname });
				aggregate_function_fields.push({ label: df.label, value: df.fieldname });
			}
			if (["Link", "Select"].includes(df.fieldtype)) {
				group_by_fields.push({ label: df.label, value: df.fieldname });
			}
		});

		return {
			date_fields: date_fields,
			value_fields: value_fields,
			group_by_fields: group_by_fields,
			aggregate_function_fields: aggregate_function_fields,
		};
	}

	remove_duplicates(items) {
		return items.filter((item, index) => items.indexOf(item) === index);
	}
};
