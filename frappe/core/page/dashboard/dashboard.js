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
			var chart_wrapper = $(`<div id="${id}" class="col-sm-6"></div>`).appendTo($("#dashboard-graph"))
			this.create_chart(`#${id}`, chart, JSON.parse(chart.chart_filters_json))
		})

	})

	$(`<div class="dashboard page-main-content">
		<div id="dashboard-graph" class="row"></div>
	</div>`).appendTo(this.page.main)

	this.timespans = ["Last Week", "Last Month", "Last Quarter", "Last Year"];
	this.timegrains = ["Daily", "Weekly", "Monthly", "Quarterly"];
	this.filters = {
		timespan: "Last Week",
		timegrain: "Daily",
		account: "Cash - GTPL",
	}

	this.account_select = this.page.add_field({
		fieldname: "account",
		label: __("Account"),
		fieldtype: "Link",
		options: "Account",
		get_query: {
			doctype: "Account",
			filters: {
				company: "Gadget Technologies Pvt. Ltd.",
			}
		}
	}).$wrapper.find("input")

	this.timespan_select = this.page.add_select(__("Time Span"),
		this.timespans.map(d => {
			return {"label": __(d), value: d }
		})
	)

	this.timegrain_select = this.page.add_select(__("Time Grain"),
		this.timegrains.map(d => {
			return {"label": __(d), value: d }
		})
	)
	this.account_select.on("change", function() {
		me.filters.account = this.value
		me.create_chart()
	});

	this.timespan_select.on("change", function() {
		me.filters.timespan = this.value
		me.create_chart()
	});

	this.timegrain_select.on("change", function() {
		me.filters.timegrain = this.value
		me.create_chart()
	});

	this.create_chart = function(wrapper, chart, filters) {
		frappe.call({
			method: "frappe.core.page.dashboard.dashboard.get_data",
			args: {
				dashboard_name: chart.chart_path,
				filters: filters,
			},
			callback: function(message) {
				const data = message.message
				var chart_args = {
					data: {
						datasets: data.datasets,
						labels: data.labels,
					},
					type: chart.chart_type,
				}
				new Chart(wrapper, chart_args)
			}
		})
	}
}