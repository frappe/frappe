import Widget from "./base_widget.js";

export default class OnboardingWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	make_body() {
		this.steps.forEach(step => {
			this.add_step(step);
		})
	}

	add_step(step) {
		let $step = $(`<div class="onboarding-step">
				<i class="fa fa-check-circle ${step.is_complete ? 'complete' : 'incomplete'}" aria-hidden="true"></i>${step.label}
			</div>`)

		$step.appendTo(this.body)
		return $step
	}

	set_body() {
		this.widget.addClass('onboarding-widget-box')
		this.make_body();
	}

	set_title() {
		super.set_title();
		let subtitle = $(`<div class="widget-subtitle">${this.subtitle}</div>`)
		subtitle.appendTo(this.title_field);
	}

	set_actions() {
		this.action_area.empty();
		const dismiss = $(`<div class="small" style="cursor:pointer;">Dismiss</div>`);
		dismiss.on('click', () => {
			this.delete();
		})
		dismiss.appendTo(this.action_area);
	}
}