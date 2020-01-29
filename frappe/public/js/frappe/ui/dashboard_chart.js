frappe.provide('ui')

frappe.ui.DashboardChart = class DashboardChart {
	constructor(chart_doc, chart_container, options) {
		this.chart_doc = chart_doc;
		this.container = chart_container;
		this.options = options;
		this.chart_args = {};
	}

	show() {
		this.get_settings().then(() => {
			this.prepare_chart_object();
			this.prepare_container();
			if (!this.options.hide_actions || this.options.hide_actions == undefined) {
				this.prepare_chart_actions();
			}
			this.fetch(this.filters).then((data) => {
				if (!this.options.hide_last_sync || this.options.hide_last_sync == undefined) {
					this.update_last_synced();
				}
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
			<div class="chart-wrapper">
				<div class="chart-loading-state text-muted">${__("Loading...")}</div>
				<div class="chart-empty-state hide text-muted">${__("No Data")}</div>
			</div>
		</div>`);
		this.chart_container.appendTo(this.container);

		if (!this.options.hide_last_sync || this.options.hide_last_sync == undefined) {
			let last_synced_text = $(`<span class="text-muted last-synced-text"></span>`);
			last_synced_text.prependTo(this.chart_container);
		}
	}

	prepare_chart_actions() {
		let actions = [
			{
				label: __("Refresh"),
				action: 'action-refresh',
				handler: () => {
					this.fetch(this.filters, true).then(data => {
						this.update_chart_object();
						this.data = data;
						this.render();
					});
				}
			},
			{
				label: __("Edit..."),
				action: 'action-edit',
				handler: () => {
					frappe.set_route('Form', 'Dashboard Chart', this.chart_doc.name);
				}
			}
		];
		if (this.chart_doc.document_type) {
			actions.push({
				label: __("{0} List", [this.chart_doc.document_type]),
				action: 'action-list',
				handler: () => {
					frappe.set_route('List', this.chart_doc.document_type);
				}
			})
		}
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
		this.chart_container.find('.chart-loading-state').removeClass('hide');
		let method = this.settings ? this.settings.method
			: 'frappe.desk.doctype.dashboard_chart.dashboard_chart.get';

		return frappe.xcall(
			method,
			{
				chart_name: this.chart_doc.name,
				filters: filters,
				refresh: refresh ? 1 : 0,
			}
		);
	}

	render() {
		this.chart_container.find('.chart-loading-state').addClass('hide');
		if (!this.data) {
			this.chart_container.find('.chart-empty-state').removeClass('hide');
		} else {
			this.prepare_chart_args();

			if (!this.chart) {
				this.chart = new frappe.Chart(this.chart_container.find(".chart-wrapper")[0], this.chart_args);
			} else {
				this.chart.update(this.data);
			}
		}
	}

	prepare_chart_args() {
		const chart_type_map = {
			"Line": "line",
			"Bar": "bar",
		};

		this.chart_args.data = this.data;
		this.chart_args.type = chart_type_map[this.chart_doc.type];
		this.chart_args.colors = [this.chart_doc.color || "light-blue"];
		this.chart_args.axisOptions = {
			xIsSeries: this.chart_doc.timeseries,
			shortenYAxisNumbers: 1
		}

		if (!this.options.hide_title || this.options.hide_title == undefined) {
			this.chart_args.title = this.chart_doc.chart_name;
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
		if (this.chart_doc.chart_type == 'Custom') {
			// custom source
			if (frappe.dashboards && frappe.dashboards.chart_sources[this.chart_doc.source]) {
				this.settings = frappe.dashboards.chart_sources[this.chart_doc.source];
				return Promise.resolve();
			} else {
				return frappe.xcall('frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config',
					{name: this.chart_doc.source})
					.then(config => {
						frappe.dom.eval(config);
						this.settings = frappe.dashboards.chart_sources[this.chart_doc.source];
					});
			}
		} else {
			return Promise.resolve();
		}
	}
}