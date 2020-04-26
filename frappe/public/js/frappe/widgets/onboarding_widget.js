import Widget from "./base_widget.js";
import { generate_route } from "./utils";

export default class OnboardingWidget extends Widget {
	constructor(opts) {
		super(opts);
		window.onb = this;
	}

	make_body() {
		this.body.addClass('grid')
		if (this.steps.length < 5) {
			this.body.addClass(`grid-rows-${this.steps.length}`)
		} else if (this.steps.length >= 5) {
			this.body.addClass('grid-rows-5')
		}
		this.steps.forEach((step) => {
			this.add_step(step);
		});
	}

	add_step(step) {
		let status = step.is_complete
			? "complete"
			: step.is_skipped
				? "skipped"
				: "";
		let $step = $(`<div class="onboarding-step ${status}" data-step-name=${step.name}>
				<i class="fa fa-check-circle" aria-hidden="true" title="${status}"></i>
				<span>${step.title}</span>
			</div>`);

		if (!step.is_mandatory && !step.is_complete) {
			// let skip_html = $(`<i class="fa fa-check text-extra-muted step-skip" title="Mark as Complete" aria-hidden="true"></i>`);
			let skip_html = $(`<span class="ml-5 small text-muted step-skip">Skip</span>`);
			skip_html.appendTo($step);
			skip_html.on('click', () => {
				this.skip_step(step, $step);
				event.stopPropagation();
			})
		}

		let action = () => {};
		if (step.action == "Watch Video") {
			action = () => {
				frappe.help.show_video(step.video_url, step.title);
				this.mark_complete(step, $step);
			}
		}

		else if (step.action == "Create Entry") {
			action = () => {
				frappe.ui.form.make_quick_entry(step.reference_document, () => {
					this.mark_complete(step, $step);
				}, null, null, true)
			}
		}

		else if (step.action == "View Settings") {
			action = () => {
				frappe.set_route("Form", step.reference_document)
			}
		}

		else if (step.action == "View Report") {
			action = () => {
				let route = generate_route({
					name: step.reference_report,
					type: 'report',
					is_query_report: ["Query Report", "Script Report"].includes(step.report_type)
				});

				frappe.set_route(route);
				this.mark_complete(step, $step);
			}
		}

		$step.on('click', action)


		$step.appendTo(this.body);
		return $step;
	}

	mark_complete(step, $step) {
		frappe.call("frappe.desk.desktop.update_onboarding_step", {
			name: step.name,
			field: 'is_complete',
			value: 1
		}).then(() => {
			step.is_complete = true;
			$step.addClass('complete');
		})

		let pending = onb.steps.filter(step => {
			return !(step.is_complete || step.is_skipped)
		})

		if (pending.length) {
			this.show_success()
		}
	}

	skip_step(step, $step) {
		frappe.call("frappe.desk.desktop.update_onboarding_step", {
			name: step.name,
			field: 'is_skipped',
			value: 1
		}).then(() => {
			step.is_skipped = true;
			$step.addClass('skipped');
		})

		let pending = onb.steps.filter(step => {
			return !(step.is_complete || step.is_skipped)
		})

		if (pending.length) {
			this.show_success()
		}
	}

	show_success() {
		let height = this.widget.height();
		this.widget.empty();
		this.widget.height(height);
		this.widget.addClass('flex');
		this.widget.addClass('align-center');
		this.widget.addClass('justify-center');

		let success = $(`<div class="success">
					<h1>Hooray 🎉</h1>
					<div class="text-muted">Your website seems good to go!</div>
			</div>
		`);
		success.appendTo(this.widget);

	};

	set_body() {
		this.widget.addClass("onboarding-widget-box");
		if (this.is_dismissed()) {
			this.widget.hide();
		} else {
			this.make_body();
		}
	}

	is_dismissed() {
		let dismissed = JSON.parse(
			localStorage.getItem("dismissed-onboarding") || "{}"
		);
		if (Object.keys(dismissed).includes(this.label)) {
			let last_hidden = new Date(dismissed[this.label]);
			let today = new Date();
			let diff = frappe.datetime.get_hour_diff(today, last_hidden);
			return diff < 24;
		}
		return false;
	}

	set_title(title) {
		super.set_title(title);
		if (this.subtitle) {
			let subtitle = $(`<div class="widget-subtitle">${this.subtitle}</div>`);
			subtitle.appendTo(this.title_field);
		}
	}

	set_actions() {
		this.action_area.empty();
		const dismiss = $(
			`<div class="small" style="cursor:pointer;">Dismiss</div>`
		);
		dismiss.on("click", () => {
			let dismissed = JSON.parse(
				localStorage.getItem("dismissed-onboarding") || "{}"
			);
			dismissed[this.label] = frappe.datetime.now_datetime();

			localStorage.setItem(
				"dismissed-onboarding",
				JSON.stringify(dismissed)
			);
			this.delete();
		});
		dismiss.appendTo(this.action_area);
	}
}
