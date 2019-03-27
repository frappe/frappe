// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt


frappe.pages['dashboard'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dashboard"),
		single_column: true
	});

	frappe.dashboard = new Dashboard(wrapper);
	$(wrapper).bind('show', function() {
		frappe.dashboard.show();
	});
};

class Dashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		$(`<div class="dashboard">
			<div class="dashboard-graph row"></div>
		</div>`).appendTo(this.wrapper.find(".page-content").empty());
		this.container = this.wrapper.find(".dashboard-graph");
		this.page = wrapper.page;
	}

	show() {
		this.route = frappe.get_route();
		const current_dashboard_name = this.route.slice(-1)[0];

		if(this.dashboard_name !== current_dashboard_name) {
			this.dashboard_name = current_dashboard_name;
			this.page.set_title(this.dashboard_name);
			this.set_dropdown();
			this.container.empty();
			this.refresh();
		}
		this.charts = {};
	}

	refresh() {
		this.get_dashboard_doc().then((doc) => {
			this.dashboard_doc = doc;
			this.charts = this.dashboard_doc.charts;

			this.charts.map((chart) => {
				let chart_container = $("<div></div>");
				chart_container.appendTo(this.container);

				frappe.model.with_doc("Dashboard Chart", chart.chart).then( chart_doc => {
					let dashboard_chart = new DashboardChart(chart_doc, chart_container);
					dashboard_chart.show();
				});
			});
		});
	}

	get_dashboard_doc() {
		return frappe.model.with_doc('Dashboard', this.dashboard_name);
	}

	set_dropdown() {
		this.page.clear_menu();
		frappe.db.get_list("Dashboard").then(dashboards => {
			dashboards.map(dashboard => {
				let name = dashboard.name;
				if(name != this.dashboard_name){
					this.page.add_menu_item(name, () => frappe.set_route("dashboard", name));
				}
			});
		});
	}
}

class DashboardChart {
	constructor(chart_doc, chart_container) {
		this.chart_doc = chart_doc;
		this.container = chart_container;
	}

	show() {
		this.get_settings().then(() => {
			this.prepare_chart_object();
			this.prepare_container();
			this.prepare_chart_actions();
			this.fetch(this.filters).then((data) => {
				this.update_last_synced();
				this.data = data;
				this.render();
			});
		});
	}

	prepare_container() {
		const column_width_map = {
			"Half": "6",
			"Full": "12",
		};
		let columns = column_width_map[this.chart_doc.width];
		this.chart_container = $(`<div class="col-sm-${columns} chart-column-container">
			<div class="chart-wrapper"></div>
		</div>`);
		this.chart_container.appendTo(this.container);

		let last_synced_text = $(`<span class="text-muted last-synced-text"></span>`);
		last_synced_text.prependTo(this.chart_container);
	}

	prepare_chart_actions() {
		let actions = [
			{
				label: __("Set Filters"),
				action: "set-filters",
				handler: this.create_set_filters_dialog.bind(this)
			},
			{
				label: __("Force Refresh"),
				action: "force-refresh",
				handler: () => {
					this.fetch(this.filters, true).then(data => {
						this.update_chart_object();
						this.data = data;
						this.render();
					});
				}
			}
		];
		this.set_chart_actions(actions);
	}

	set_chart_actions(actions) {
		this.chart_actions = $(`<div class="chart-actions btn-group dropdown pull-right">
			<a class="dropdown-toggle" data-toggle="dropdown"
				aria-haspopup="true" aria-expanded="false"> <button class="btn btn-default btn-xs"><span class="caret"></span></button>
			</a>
			<ul class="dropdown-menu" style="max-height: 300px; overflow-y: auto;">
				${actions.map(action => `<li><a data-action="${action.action}">${action.label}</a></li>`).join('')}
			</ul>
		</div>
		`);

		this.chart_actions.find("a[data-action]").each((i, o) => {
			const action = o.dataset.action;
			$(o).click(actions.find(a => a.action === action));
		});
		this.chart_actions.prependTo(this.chart_container);
	}

	fetch(filters, refresh=false) {
		return frappe.xcall(
			this.settings.method_path,
			{
				chart_name: this.chart_doc.name,
				filters: filters,
				refresh: refresh ? 1 : 0,
			}
		);
	}

	render() {
		const chart_type_map = {
			"Line": "line",
			"Bar": "bar",
		};
		let chart_args = {
			title: this.chart_doc.chart_name.bold(),
			data: this.data,
			type: chart_type_map[this.chart_doc.type],
			colors: [this.chart_doc.color || "light-blue"],
			axisOptions: {
				xIsSeries: this.settings.is_time_series
			},
		};
		if(!this.chart) {
			this.chart = new Chart(this.chart_container.find(".chart-wrapper")[0], chart_args);
		} else {
			this.chart.update(this.data);
		}
	}

	update_last_synced() {
		let last_synced_text = __("Last synced {0}", [comment_when(this.chart_doc.last_synced_on)]);
		this.container.find(".last-synced-text").html(last_synced_text);
	}

	update_chart_object() {
		frappe.db.get_doc("Dashboard Chart", this.chart_doc.name).then(doc => {
			this.chart_doc = doc;
			this.prepare_chart_object();
			this.update_last_synced();
		});
	}

	prepare_chart_object() {
		this.filters = JSON.parse(this.chart_doc.filters_json || '{}');
	}

	get_settings() {
		return new Promise(resolve => frappe.db.get_value("Dashboard Chart Source", this.chart_doc.source, "config", e => {
			this.settings = JSON.parse(e.config);
			resolve();
		}));
	}

	create_set_filters_dialog() {
		const d = new frappe.ui.Dialog({
			title: __('Set Filters'),
			fields: this.settings.filters
		});
		d.set_values(this.filters);
		d.show();

		const set_filters = () => {
			const values = d.get_values();
			if (!Object.entries(this.filters).map(e => values[e[0]] === e[1]).every(Boolean)) {
				frappe.db.set_value("Dashboard Chart", this.chart_doc.name, "filters_json", JSON.stringify(values)).then(() => {
					this.fetch(values, true).then(data => {
						this.update_chart_object();
						this.data = data;
						this.render();
					});
				});
			}
			d.hide();
		};

		this.settings.filters.map(field => field.onchange = e => {
			if(e) {
				d.set_primary_action(__('Save Filters'), set_filters);
			}
		});
	}
}