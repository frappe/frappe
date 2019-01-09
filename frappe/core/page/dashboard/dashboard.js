frappe.pages['dashboard'].on_page_load = function(wrapper) {
	var me = this
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Dashboard',
		single_column: true
	})

	$(`<div class="dashboard page-main-content">
		<div id="dashboard-graph"></div>
	</div>`).appendTo(this.page.main)

	this.timespans = ["Last Week", "Last Month", "Last Quarter", "Last Year"];
	this.filters = {
		timespan: "Week",
	}
	this.timespan_select = this.page.add_select(__("Timespan"),
		this.timespans.map(d => {
			return {"label": __(d), value: d }
		})
	)

	this.timespan_select.on("change", function() {
		me.filters.timespan = this.value
		me.create_chart()
	});

	this.create_chart = function() {
		frappe.call({
			method: "frappe.core.page.dashboard.dashboard.get_data",
			args: {
				dashboard_name: "erpnext.accounts.dashboard.get",
				filters: this.filters,
			},
			callback: function(message) {
				const data = message.message
				var chart_args = {
					data: {
						datasets: data.datasets,
						labels: data.labels,
					},
					type: 'line',
				}
				new Chart('#dashboard-graph', chart_args)
			}
		})
	}

	this.create_chart()
}