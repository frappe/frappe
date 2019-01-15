frappe.pages['dashboard'].on_page_load = function(wrapper) {
	var me = this

	this.route = frappe.get_route()
	this.dashboard_name = this.route.slice(-1)[0]
	this.dashboard_doc = null

	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: this.dashboard_name,
		single_column: true
	})

	frappe.model.with_doc('Dashboard', this.dashboard_name).then((doc) => {
		this.dashboard_doc = doc
		this.charts = this.dashboard_doc.charts

		this.charts.map((chart) => {
			var id = `dashboard-chart-${chart.name}`

			const column_width_map = {
				"Half": "6",
				"Full": "12",
			}
			var columns = column_width_map[chart.chart_width]
			var chart_wrapper = $(`<div class="col-sm-${columns}"><div id="${id}"></div></div>`)
			chart_wrapper.appendTo($("#dashboard-graph"))

			this.create_chart(`#${id}`, chart, JSON.parse(chart.chart_filters_json))
		})

	})

	$(`<div class="dashboard page-main-content">
		<div id="dashboard-graph" class="row"></div>
	</div>`).appendTo(this.page.main)

	this.create_chart = function(wrapper, chart, filters) {
		frappe.call({
			method: "frappe.core.page.dashboard.dashboard.get_data",
			args: {
				dashboard_name: chart.chart_path,
				filters: filters,
			},
			callback: function(message) {
				const chart_type_map = {
					"Line": "line",
					"Bar": "bar",
				}
				const data = message.message
				var chart_args = {
					title: chart.chart_name,
					data: {
						datasets: data.datasets,
						labels: data.labels,
					},
					type: chart_type_map[chart.chart_type],
				}
				new Chart(wrapper, chart_args)
			}
		})
	}
}