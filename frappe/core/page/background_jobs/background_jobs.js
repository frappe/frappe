frappe.pages["background_jobs"].on_page_load = (wrapper) => {
	const background_job = new BackgroundJobs(wrapper);

	$(wrapper).bind("show", () => {
		background_job.show();
	});

	window.background_jobs = background_job;
};

class BackgroundJobs {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Background Jobs"),
			single_column: true,
		});

		this.page.add_inner_button(__("Remove Failed Jobs"), () => {
			frappe.confirm(__("Are you sure you want to remove all failed jobs?"), () => {
				frappe
					.call("frappe.core.page.background_jobs.background_jobs.remove_failed_jobs")
					.then(() => this.refresh_jobs());
			});
		});

		this.page.main.addClass("frappe-card");
		this.page.body.append('<div class="table-area"></div>');
		this.$content = $(this.page.body).find(".table-area");

		this.make_filters();
		this.refresh_jobs = frappe.utils.throttle(this.refresh_jobs.bind(this), 1000);
	}

	make_filters() {
		this.view = this.page.add_field({
			label: __("View"),
			fieldname: "view",
			fieldtype: "Select",
			options: ["Jobs", "Workers"],
			default: "Jobs",
			change: () => {
				this.queue_timeout.toggle(this.view.get_value() === "Jobs");
				this.job_status.toggle(this.view.get_value() === "Jobs");
			},
		});
		this.queue_timeout = this.page.add_field({
			label: __("Queue"),
			fieldname: "queue_timeout",
			fieldtype: "Select",
			options: [
				{ label: "All Queues", value: "all" },
				{ label: "Default", value: "default" },
				{ label: "Short", value: "short" },
				{ label: "Long", value: "long" },
			],
			default: "all",
		});
		this.job_status = this.page.add_field({
			label: __("Job Status"),
			fieldname: "job_status",
			fieldtype: "Select",
			options: [
				{ label: "All Jobs", value: "all" },
				{ label: "Queued", value: "queued" },
				{ label: "Deferred", value: "deferred" },
				{ label: "Started", value: "started" },
				{ label: "Finished", value: "finished" },
				{ label: "Failed", value: "failed" },
			],
			default: "all",
		});
		this.auto_refresh = this.page.add_field({
			label: __("Auto Refresh"),
			fieldname: "auto_refresh",
			fieldtype: "Check",
			default: 1,
			change: () => {
				if (this.auto_refresh.get_value()) {
					this.refresh_jobs();
				}
			},
		});
	}

	show() {
		this.refresh_jobs();
		this.update_scheduler_status();
	}

	update_scheduler_status() {
		frappe.call({
			method: "frappe.core.page.background_jobs.background_jobs.get_scheduler_status",
			callback: (r) => {
				let { status } = r.message;
				if (status === "active") {
					this.page.set_indicator(__("Scheduler: Active"), "green");
				} else {
					this.page.set_indicator(__("Scheduler: Inactive"), "red");
				}
			},
		});
	}

	refresh_jobs() {
		let view = this.view.get_value();
		let args;
		let { queue_timeout, job_status } = this.page.get_form_values();
		if (view === "Jobs") {
			args = { view, queue_timeout, job_status };
		} else {
			args = { view };
		}

		this.page.add_inner_message(__("Refreshing..."));
		frappe.call({
			method: "frappe.core.page.background_jobs.background_jobs.get_info",
			args,
			callback: (res) => {
				this.page.add_inner_message("");

				let template = view === "Jobs" ? "background_jobs" : "background_workers";
				this.$content.html(
					frappe.render_template(template, {
						jobs: res.message || [],
					})
				);

				let auto_refresh = this.auto_refresh.get_value();
				if (frappe.get_route()[0] === "background_jobs" && auto_refresh) {
					setTimeout(() => this.refresh_jobs(), 2000);
				}
			},
		});
	}
}
