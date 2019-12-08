// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("frappe.setup");
frappe.provide("frappe.ui");

frappe.setup.OnboardingSlide = class OnboardingSlide extends frappe.ui.Slide {
	constructor(slide = null) {
		super(slide);
	}

	make() {
		super.make();
		this.$next_btn = this.slides_footer.find('.next-btn');
		this.$complete_btn = this.slides_footer.find('.complete-btn');
		this.$action_button = this.slides_footer.find('.next-btn');
		if (this.help_links) {
			this.$help_links = $(`<div class="text-center">
				<div class="help-links"></div>
			</div>`).appendTo(this.$body);
			this.setup_help_links();
		}
	}

	setup_form() {
		super.setup_form();
		const fields = this.get_atomic_fields();
		if (fields.length == 1) {
			this.$form_wrapper.addClass("text-center");
		} else {
			this.$form_wrapper.removeClass("text-center");
		}
	}

	before_show() {
		(this.id === 0) ?
			this.$next_btn.text(__('Let\'s Start')) : this.$next_btn.text(__('Next'));
		//last slide
		if (this.is_last_slide()) {
			this.$complete_btn.removeClass('hide').addClass('action primary');
			this.$next_btn.removeClass('action primary');
			this.$action_button = this.$complete_btn;
		}
		this.setup_action_button();
	}

	primary_action() {
		if (this.set_values()) {
			this.$action_button.addClass('disabled');
			const primary_method = 'frappe.desk.doctype.onboarding_slide.onboarding_slide.create_onboarding_docs';
			if (this.add_more) {
				this.values.max_count = this.max_count;
			}
			frappe.call(primary_method, {
				values: this.values,
				doctype: this.ref_doctype,
				app: this.app,
				slide_type: this.slide_type
			}).then(() => {
				if (this.is_last_slide()) {
					this.reset_is_first_startup();
					$('.onboarding-dialog').modal('toggle');
					frappe.msgprint({
						message: __('You are all set up!'),
						indicator: 'green',
						title: __('Success')
					});
				}
			});
		}
	}

	unbind_primary_action() {
		// unbind only action method as next button is same as create button in this setup wizard
		this.$action_button.off('click.primary_action');
	}

	setup_help_links() {
		this.help_links.map(link => {
			let $link = $(
				`<a target="_blank" class="small text-muted">${link.label || __("Need Help?")}</a>`
			);
			if (link.video_id) {
				$link.on('click', () => {
					frappe.help.show_video(link.video_id, link.label);
				});
			}
			this.$help_links.append($link);
		});
	}

	setup_action_button() {
		if (this.slide_type === 'Create' || this.slide_type == 'Settings' || this.is_last_slide()) {
			this.$action_button.addClass('primary');
		} else {
			this.$action_button.removeClass('primary');
		}

		this.$action_button.on('click', () => {
			if (this.slide_type != 'Continue') {
				this.mark_as_completed();
			}
		});
	}

	mark_as_completed() {
		frappe.call({
			method: 'frappe.desk.doctype.onboarding_slide.onboarding_slide.mark_slide_as_completed',
			args: {slide_title: this.title},
			callback: () => {},
			freeze: true
		});
	}

	reset_is_first_startup() {
		frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.reset_is_first_startup",
			args: {},
			callback: () => {}
		});
	}
};

frappe.setup.OnboardingDialog  = class OnboardingDialog {
	constructor({
		slides = []
	}) {
		this.slides = slides;
		this.setup();
	}

	setup() {
		this.dialog = new frappe.ui.Dialog({
			static: true,
			minimizable: false,
		});
		this.$wrapper = $(this.dialog.$wrapper).addClass('onboarding-dialog');
		this.slide_container = new frappe.ui.Slides({
			parent: this.dialog.body,
			slides: this.slides,
			slide_class: frappe.setup.OnboardingSlide,
			unidirectional: 1,
			before_load: ($footer) => {
				$footer.find('.prev-btn').addClass('hide');
				$footer.find('.next-btn').removeClass('btn-default').addClass('btn-primary action');
				$footer.find('.text-right').prepend(
					$(`<a class="complete-btn btn btn-primary btn-sm hide">
				${__("Complete")}</a>`));
			}
		});

		this.$wrapper.find('.modal-header').remove();
	}

	show() {
		this.dialog.show();
	}
};
