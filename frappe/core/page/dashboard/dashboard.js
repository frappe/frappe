frappe.pages['dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Dashboard',
		single_column: true
	});

	$(`<div class="dashboard page-main-content">
		<div class="dashboard-graph"></div>
	</div>`).appendTo(this.page.main);

	frappe.call({
		method: "frappe.core.page.dashboard.dashboard.get_data",
		args: {
			dashboard_name: "erpnext.accounts.dashboard.get",
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
			new Chart('.dashboard-graph', chart_args)
		}
	})
}