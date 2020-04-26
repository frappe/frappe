import Widget from "./base_widget.js";
import { generate_route } from "./utils";

export default class OnboardingWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	make_body() {
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
		let $step = $(`<div class="onboarding-step ${
					step.is_complete ? 'complete' : 'incomplete'
				}" data-step-name=${step.name}>
				<i class="fa fa-check-circle" aria-hidden="true"></i>
				<span>${step.title}</span>
			</div>`);

		if (!step.is_complete) {
			let action = () => {};
			if (step.action == "Watch Video") {
				action = () => {
					frappe.help.show_video(step.video_url, step.title);
					this.mark_complete(step.name, $step);
				}
			}

			else if (step.action == "Create Entry") {
				action = () => {
					frappe.ui.form.make_quick_entry(step.reference_document, () => {
						this.mark_complete(step.name, $step);
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
					this.mark_complete(step.name, $step);
				}
			}

			$step.on('click', action)
		}

		$step.appendTo(this.body);
		return $step;
	}

	mark_complete(name, $step) {
		frappe.call("frappe.desk.desktop.complete_onboarding_step", {
			name: name
		}).then(() => {
			$step.removeClass('incomplete')
			$step.addClass('complete')
		})
	}

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
