frappe.pages["background_jobs"].on_page_load = (wrapper) => {
	const background_job = new BackgroundJobs(wrapper);

	$(wrapper).bind('show', () => {
		background_job.show();
	});

	window.background_jobs = background_job;
};

class BackgroundJobs {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('Background Jobs'),
			single_column: true
		});

		this.called = false;
		this.show_failed = false;

		this.show_failed_button = this.page.add_inner_button(__("Show Failed Jobs"), () => {
			this.show_failed = !this.show_failed;
			if (this.show_failed_button) {
				this.show_failed_button.text(
					this.show_failed ? __("Hide Failed Jobs") : __("Show Failed Jobs")
				);
			}
		});

		// add a "Remove Failed Jobs button"
		this.remove_failed_button = this.page.add_inner_button(__("Remove Failed Jobs"), () => {
			frappe.call({
				method: 'frappe.core.page.background_jobs.background_jobs.remove_failed_jobs',
				callback: () => {
					this.refresh_jobs();
				}
			});
		});

		$(frappe.render_template('background_jobs_outer')).appendTo(this.page.body);
		this.content = $(this.page.body).find('.table-area');
	}

	show() {
		this.refresh_jobs();
		frappe.call({
			method: 'frappe.core.page.background_jobs.background_jobs.get_scheduler_status',
			callback: res => {
				this.page.set_indicator(...res.message);
			}
		});
	}

	refresh_jobs() {
		if (this.called) return;
		this.called = true;

		frappe.call({
			method: 'frappe.core.page.background_jobs.background_jobs.get_info',
			args: {
				show_failed: this.show_failed
			},
			callback: (res) => {
				this.called = false;
				this.page.body.find('.list-jobs').remove();
				$(frappe.render_template('background_jobs', { jobs: res.message || [] })).appendTo(this.content);

				if (frappe.get_route()[0] === 'background_jobs') {
					setTimeout(() => this.refresh_jobs(), 2000);
				}
			}
		});
	}
}
