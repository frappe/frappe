import Widget from "./base_widget.js";

export default class ChartWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	refresh() {
		//
	}

	customize() {
		this.setup_customize_actions();
	}

	make_chart() {
		this.body.empty()
		frappe.model.with_doc("Dashboard Chart", this.chart_name).then(chart_doc => {
			chart_doc.width = 'Full'
			this.dashboard = new frappe.ui.DashboardChart(chart_doc, this.body, { hide_title: true, hide_last_sync: true, hide_actions: true });
			this.dashboard.show();
		});

		this.summary && this.set_summary();
	}

	set_body() {
		this.widget.addClass('dashboard-widget-box')
		this.make_chart();
	}

	set_summary() {
		let summary = $(`<span class="dashboard-summary">$ 54,231</span>`);
		this.title_field.addClass('text-muted')
		summary.appendTo(this.body);
	}

	setup_events() {
		//
	}

	setup_customize_actions() {
		this.action_area.empty()
		const buttons = $(`<button type="button" class="btn btn-xs btn-secondary btn-default selected">Resize</button>
					<button class="btn btn-secondary btn-light btn-danger btn-xs"><i class="fa fa-trash" aria-hidden="true"></i></button>`);
		buttons.appendTo(this.action_area);
	}

	set_actions() {
		return
		this.action_area.empty()
		const buttons = $(`<div class="btn-group btn-group-xs" role="group" aria-label="Basic example">
						<button type="button" class="btn btn-secondary btn-default selected">Monthly</button>
						<button type="button" class="btn btn-secondary btn-default">Quaterly</button>
						<button type="button" class="btn btn-secondary btn-default">Yearly</button>
					</div>
					<button class="btn btn-secondary btn-light btn-default btn-xs"><i class="fa fa-refresh" aria-hidden="true"></i></button>`);
		buttons.appendTo(this.action_area);
	}
}