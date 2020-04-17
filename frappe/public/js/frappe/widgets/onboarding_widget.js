import Widget from "./base_widget.js";

export default class OnboardingWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	make_body() {
		this.steps.forEach((step) => {
			this.add_step(step);
		});
	}

	add_step(step) {
		let $step = $(`<div class="onboarding-step">
				<i class="fa fa-check-circle ${
					step.is_complete ? "complete" : "incomplete"
				}" aria-hidden="true"></i>${step.label}
			</div>`);

		$step.appendTo(this.body);
		return $step;
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
		let dismissed = JSON.parse(localStorage.getItem("dismissed-onboarding") || '{}');
		if (Object.keys(dismissed).includes(this.label)) {
			let last_hidden = new Date(dismissed[this.label]);
			let today = new Date();
			let diff = frappe.datetime.get_hour_diff(today, last_hidden)
			return diff < 24;
		}
		return false
	}

	set_title(title) {
		super.set_title(title);
		let subtitle = $(`<div class="widget-subtitle">${this.subtitle}</div>`);
		subtitle.appendTo(this.title_field);
	}

	set_actions() {
		this.action_area.empty();
		const dismiss = $(
			`<div class="small" style="cursor:pointer;">Dismiss</div>`
		);
		dismiss.on("click", () => {
			let dismissed = JSON.parse(localStorage.getItem("dismissed-onboarding") || '{}');
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