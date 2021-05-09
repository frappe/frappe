frappe.provide('frappe.cpu_usage');
frappe.pages['analytics'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Usage Analytics',
		single_column: false
	});

	// Running the socketio background job
	frappe.call({
		method: "frappe.core.page.analytics.analytics.run_cpu_job",
		callback: function(r) {}
	});
	// Initializing the CPU page
	frappe.cpu_usage = new CpuPage(page);
}

class CpuPage {
	constructor(page) {
		this.page = page;
		this.currentPoints = 0;
		this.maxCpuUsage = 0;
		$(frappe.render_template("analytics", {})).appendTo(this.page.main);
		const data = {
			labels: [],
			datasets: [
				{
					values: []
				}
			],
		};
		// Real Time CPU usage chart
		this.cpuChart = new frappe.Chart("#chartz", {
			title: "CPU Usage",
			data: data,
			type: 'line',
			height: 250,
			colors: ['blue'],
			lineOptions: {
				regionFill: 1
			},
		});
		frappe.require(['/assets/js/raphael.min.js', '/assets/js/justgage.js'], () => {
			//CPU frequency Gauge
			this.gauge1 = new JustGage({
				id: 'gauge1',
				value: 50,
				min: 0,
				max: 10000,
				minLabelMinFontSize: 16,
				maxLabelMinFontSize: 16,
				labelMinFontSize: 14,
				textRenderer: (value) => {return (value/1000).toFixed(2) + ' ghz'}
			});
			//Maximum CPU usage Gauge
			this.gauge2 = new JustGage({
				id: 'gauge2',
				value: 50,
				min: 0,
				max: 100,
				minLabelMinFontSize: 16,
				maxLabelMinFontSize: 16,
				labelMinFontSize: 14,
				textRenderer: (value) => {return Math.round(value) + ' %'}
			});
		})
		this.setUpSocket();
	}
	setUpSocket() {
		frappe.realtime.on('cpu_page', (data) => {
			this.maxCpuUsage = Math.max(this.maxCpuUsage, data.cpu_usage);
			this.updateCpuChart(data.cpu_usage);
			this.updateProcess("user-process", data.user_process_count);
			this.updateProcess("system-process", data.root_process_count);
			this.updateProcess("all-process", data.total_process_count);
			this.gauge1.refresh(data.cpu_frequency);
			this.gauge2.refresh(this.maxCpuUsage);
		});
	}
	updateProcess(process_id, data) {
		$(`#${process_id}`).text(data);
	}
	updateCpuChart(cpu_usage) {
		const value = [cpu_usage];
		this.currentPoints++;
		if (this.currentPoints > 8) {
			this.cpuChart.removeDataPoint(0);
		}
		this.cpuChart.addDataPoint(new Date().toLocaleTimeString(), value);
	}
}
