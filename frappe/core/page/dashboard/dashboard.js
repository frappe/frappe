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
		this.charts = {}
	}

	refresh() {
		this.get_dashboard_doc().then((doc) => {
			this.dashboard_doc = doc
			this.charts = this.dashboard_doc.charts

			this.charts.map((chart_doc) => {
				let chart_container = $("<div><div>")
				chart_container.appendTo(this.container)

				let dashboard_chart = new DashboardChart(chart_doc, chart_container)
				dashboard_chart.show()
			})
		})
	}

	get_dashboard_doc() {
		return frappe.model.with_doc('Dashboard', this.dashboard_name)
	}
}

class DashboardChart {
	constructor(chart_doc, chart_container) {
		this.chart_doc = chart_doc
		this.container = chart_container
	}

	show() {
		this.filters = JSON.parse(this.chart_doc.filters_json || '{}')
		this.filter_fields = JSON.parse(this.chart_doc.filter_fields || '[]')

		this.prepare_container()

		this.fetch().then((data) => {
			this.data = data
			this.render()
		})
	}

	prepare_container() {
		const column_width_map = {
			"Half": "6",
			"Full": "12",
		}
		let columns = column_width_map[this.chart_doc.width]
		this.chart_container = $(`<div class="col-sm-${columns} chart-column-container">
			<div class="chart-wrapper"></div>
		</div>`)
		this.chart_container.appendTo(this.container)
	}

	fetch(refresh=false) {
		return frappe.xcall(
			"frappe.core.page.dashboard.dashboard.get_data",
			{
				chart_name: this.chart_doc.name,
				refresh: refresh,
			}
		)
	}

	render() {

		// var me = this
		// let actions = [
		// 	{
		// 		label: __("Set Filters"),
		// 		action: "set-filters",
		// 		handler() {
		// 			const d = new frappe.ui.Dialog({
		// 				title: __('Set Filters'),
		// 				fields: chart.filter_fields,
		// 				primary_action: function() {
		// 					const values = this.get_values()
		// 					if (!Object.entries(chart.filters_json).map(e => values[e[0]] === e[1]).every(Boolean)) {
		// 						frappe.db.set_value("Dashboard Chart", chart.name, "filters_json", JSON.stringify(values)).then(() => {
		// 							me.fetch_chart(chart).then(data => {
		// 								me.charts[chart.name].update(data)
		// 							})
		// 						})
		// 					}
		// 					this.hide()
		// 				},
		// 				primary_action_label: __('Save Filters')
		// 			})
		// 			d.set_values(chart.filters_json)
		// 			d.show();
		// 		}
		// 	},
		// 	{
		// 		label: __("Force Refresh"),
		// 		action: "force-refresh",
		// 		handler() {
		// 			me.fetch_chart(chart, true).then(data => {
		// 				me.charts[chart.name].update(data)
		// 			})
		// 		}
		// 	}
		// ]

		// let last_synced_text = $(`<span class="text-muted last-synced-text">${__("Last synced {0}", [comment_when(chart.last_synced_on)])}</span>`)
		// let chart_action = $(`<div class="chart-actions btn-group dropdown pull-right">
		// 	<a class="dropdown-toggle" data-toggle="dropdown"
		// 		aria-haspopup="true" aria-expanded="false"> <button class="btn btn-default btn-xs"><span class="caret"></span></button>
		// 	</a>
		// 	<ul class="dropdown-menu" style="max-height: 300px; overflow-y: auto;">
		// 		${actions.map(action => `<li><a data-action="${action.action}">${action.label}</a></li>`).join('')}
		// 	</ul>
		// </div>
		// `);

		// chart_action.find("a[data-action]").each((i, o) => {
		// 	const action = o.dataset.action
		// 	$(o).click(actions.find(a => a.action === action))
		// })



		// chart_action.prependTo(chart_container)
		// last_synced_text.prependTo(chart_container)

		const chart_type_map = {
			"Line": "line",
			"Bar": "bar",
		}
		let chart_args = {
			title: this.chart_doc.chart_name,
			data: {
				datasets: this.data.datasets,
				labels: this.data.labels,
			},
			type: chart_type_map[this.chart_doc.type],
			colors: [this.chart_doc.color || "light-blue"],
		};
		this.chart = new Chart(this.chart_container.find(".chart-wrapper")[0], chart_args);
	}

}