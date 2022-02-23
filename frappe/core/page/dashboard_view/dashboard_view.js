// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.dashboards');
frappe.provide('frappe.dashboards.chart_sources');


frappe.pages['dashboard-view'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dashboard"),
		single_column: true
	});

	frappe.dashboard = new Dashboard(wrapper);
	$(wrapper).bind('show', function () {
		frappe.dashboard.show();
	});
};

class Dashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		$(`<div class="dashboard" style="overflow: visible">
			<div class="dashboard-graph"></div>
		</div>`).appendTo(this.wrapper.find(".page-content").empty());
		this.container = this.wrapper.find(".dashboard-graph");
		this.page = wrapper.page;
	}

	show() {
		this.route = frappe.get_route();
		this.set_breadcrumbs();
		if (this.route.length > 1) {
			// from route
			this.show_dashboard(this.route.slice(-1)[0]);
		} else {
			// last opened
			if (frappe.last_dashboard) {
				frappe.set_re_route('dashboard-view', frappe.last_dashboard);
			} else {
				// default dashboard
				frappe.db.get_list('Dashboard', { filters: { is_default: 1 } }).then(data => {
					if (data && data.length) {
						frappe.set_re_route('dashboard-view', data[0].name);
					} else {
						// no default, get the latest one
						frappe.db.get_list('Dashboard', { limit: 1 }).then(data => {
							if (data && data.length) {
								frappe.set_re_route('dashboard-view', data[0].name);
							} else {
								// create a new dashboard!
								frappe.new_doc('Dashboard');
							}
						});
					}
				});
			}
		}
	}

	show_dashboard(current_dashboard_name) {
		if (this.dashboard_name !== current_dashboard_name) {
			this.dashboard_name = current_dashboard_name;
			let title = this.dashboard_name;
			if (!this.dashboard_name.toLowerCase().includes(__('dashboard'))) {
				// ensure dashboard title has "dashboard"
				title = __('{0} Dashboard', [title]);
			}
			this.page.set_title(title);
			this.set_dropdown();
			this.container.empty();
			this.refresh();
		}
		this.charts = {};
		frappe.last_dashboard = current_dashboard_name;
	}

	set_breadcrumbs() {
		frappe.breadcrumbs.add("Desk", "Dashboard");
	}

	refresh() {
		frappe.run_serially([
			() => this.render_cards(),
			() => this.render_charts(),
		]);
	}

	render_charts() {
		return this.get_permitted_items(
			'frappe.desk.doctype.dashboard.dashboard.get_permitted_charts'
		).then(charts => {
			if (!charts.length) {
				frappe.msgprint(__('No Permitted Charts on this Dashboard'), __('No Permitted Charts'))
			}

			frappe.dashboard_utils.get_dashboard_settings().then((settings) => {
				let chart_config = settings.chart_config ? JSON.parse(settings.chart_config) : {};
				this.charts =
					charts.map(chart => {
						return {
							chart_name: chart.chart,
							label: chart.chart,
							chart_settings: chart_config[chart.chart] || {},
							...chart
						}
					});

				this.chart_group = new frappe.widget.WidgetGroup({
					title: null,
					container: this.container,
					type: "chart",
					columns: 2,
					options: {
						allow_sorting: false,
						allow_create: false,
						allow_delete: false,
						allow_hiding: false,
						allow_edit: false,
					},
					widgets: this.charts,
				});
				this.setup_global_filters();

			})
		});
	}

	render_cards() {
		return this.get_permitted_items(
			'frappe.desk.doctype.dashboard.dashboard.get_permitted_cards'
		).then(cards => {
			if (!cards.length) {
				return;
			}

			this.number_cards =
				cards.map(card => {
					return {
						name: card.card,
					};
				});

			this.number_card_group = new frappe.widget.WidgetGroup({
				container: this.container,
				type: "number_card",
				columns: 3,
				options: {
					allow_sorting: false,
					allow_create: false,
					allow_delete: false,
					allow_hiding: false,
					allow_edit: false,
				},
				widgets: this.number_cards,
			});
		});
	}

	get_permitted_items(method) {
		return frappe.xcall(
			method,
			{
				dashboard_name: this.dashboard_name
			}
		).then(items => {
			return items;
		});
	}

	setup_global_filters() {
		let me = this;
		this.global_filter = $(
			`<div><div class="global-filter btn btn-default float-right mt-2 btn-xs">
				${frappe.utils.icon('filter', 'sm')} Filter
			</div><div>`
		);
		let container = this.wrapper.find('.widget-group').first();
		this.global_filter.appendTo(container);
		
		let fields = [
			{
				"fieldtype": "Section Break"
			},
			{
				"fieldname": "period",
				"label": "Period",
				"fieldtype": "Select",
				"options": [
					{
						"value": "Monthly",
						"label": "Monthly"
					},
					{
						"value": "Quarterly",
						"label": "Quarterly"
					},
					{
						"value": "Half-Yearly",
						"label": "Half-Yearly"
					},
					{
						"value": "Yearly",
						"label": "Yearly"
					}
				],
				"default": "Monthly"
			},
			{
				"fieldname": "fiscal_year",
				"label": "Fiscal Year",
				"fieldtype": "Link",
				"options": "Fiscal Year",
			},
			{
				"fieldname": "company",
				"label": "Company",
				"fieldtype": "Link",
				"width": "80",
				"options": "Company",
			},
			{
				"fieldname": "from_date",
				"label": "From Date",
				"fieldtype": "Date",
				"width": "80",
			},
			{
				"fieldname": "to_date",
				"label": "To Date",
				"fieldtype": "Date",
				"width": "80",
			}
		];
		//get the chart doc object
		let charts = this.chart_group.widgets_list
		let dialog = new frappe.ui.Dialog({
			title: __("Set Filters for all charts"),
			fields: fields,
			primary_action: function () {
				let values = this.get_values();
				if (values) {
					charts.map((chart) => {
						this.hide();
						//Sets the filters only of those fields which has been updated
						for(var value in values) {
						chart.filters[value] = values[value];
						me.update_charts(chart)
						}
					})

				}
			},
			primary_action_label: "Set"
		});

		this.global_filter.on("click", () => {
			dialog.show();
		})
	}

	update_charts(chart) {
			chart.save_chart_config_for_user({'filters': chart.chart_settings.filters});
			chart.fetch_and_update_chart();
	}

	set_dropdown() {
		this.page.clear_menu();

		this.page.add_menu_item(__('Edit'), () => {
			frappe.set_route('Form', 'Dashboard', frappe.dashboard.dashboard_name);
		});

		this.page.add_menu_item(__('New'), () => {
			frappe.new_doc('Dashboard');
		});

		this.page.add_menu_item(__('Refresh All'), () => {
			this.chart_group &&
				this.chart_group.widgets_list.forEach(chart => chart.refresh());
			this.number_card_group &&
				this.number_card_group.widgets_list.forEach(card => card.render_card());
		});

		frappe.db.get_list('Dashboard').then(dashboards => {
			dashboards.map(dashboard => {
				let name = dashboard.name;
				if (name != this.dashboard_name) {
					this.page.add_menu_item(name, () => frappe.set_route("dashboard-view", name), 1);
				}
			});
		});
	}
}