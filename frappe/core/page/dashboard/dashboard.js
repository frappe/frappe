frappe.pages['dashboard'].on_page_load = function(wrapper) {


	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dashboard"),
		single_column: true
	})

	frappe.dashboard = new Dashboard(wrapper)
	$(wrapper).bind('show', function() {
		frappe.dashboard.show()
	})

}

class Dashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper)
		$(`<div class="dashboard">
			<div class="dashboard-graph" class="row"></div>
		</div>`).appendTo(this.wrapper.find(".page-content").empty())
		this.container = this.wrapper.find(".dashboard-graph")
		this.page = wrapper.page
	}

	show() {
		this.route = frappe.get_route()
		const current_dashboard_name = this.route.slice(-1)[0]

		if(this.dashboard_name !== current_dashboard_name) {
			this.dashboard_name = current_dashboard_name
			this.page.set_title(this.dashboard_name)
			this.refresh()
		}
	}

	refresh() {
		this.get_dashboard_doc().then((doc) => {
			this.dashboard_doc = doc
			this.charts = this.dashboard_doc.charts

			this.charts.map((chart) => {
				this.fetch_and_render_chart(chart);
			})
		})
	}

	fetch_and_render_chart(chart) {
		this.fetch_chart(chart).then((data) => this.render_chart(chart, data))
	}

	get_dashboard_doc() {
		return frappe.model.with_doc('Dashboard', this.dashboard_name)
	}

	fetch_chart(chart) {
		return frappe.xcall(
			"frappe.core.page.dashboard.dashboard.get_data",
			{
				dashboard_name: chart.chart_path,
				filters: JSON.parse(chart.chart_filters_json),
			}
		)
	}

	render_chart(chart, data) {
		const column_width_map = {
			"Half": "6",
			"Full": "12",
		};
		let columns = column_width_map[chart.chart_width];
		let chart_container = $(`<div class="col-sm-${columns}"><div class="chart-wrapper"></div></div>`);
		chart_container.appendTo(this.container);


		const chart_type_map = {
			"Line": "line",
			"Bar": "bar",
		};
		let chart_args = {
			title: chart.chart_name,
			data: {
				datasets: data.datasets,
				labels: data.labels,
			},
			type: chart_type_map[chart.chart_type],
		};
		new Chart(chart_container.find(".chart-wrapper")[0], chart_args);
	}
}