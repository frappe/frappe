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
		this.$action_button = this.slides_footer.find('.next-btn')
		if (this.help_links) {
			this.$help_links = $(`<div class="text-center">
				<div class="help-links"></div>
			</div>`).appendTo(this.$body);
			this.setup_help_links();
		}
	}

	before_show() {
		(this.id === 0) ?
			this.$next_btn.text(__('Start')) : this.$next_btn.text(__('Next'));
		//last slide
		if (this.id === this.parent[0].children.length-1) {
			this.$complete_btn.removeClass('hide').addClass('action primary');
			this.$next_btn.removeClass('action primary');
			this.$action_button = this.$complete_btn;
		}
		this.setup_action_button();
	}

	primary_action() {
		let me = this;
		if (this.set_values()) {
			this.$action_button.addClass('disabled');
			if (me.add_more) me.values.max_count = me.max_count;
			frappe.call({
				method: 'frappe.desk.doctype.setup_wizard_slide.setup_wizard_slide.create_onboarding_docs',
				args: {
					values:me.values,
					doctype:me.ref_doctype,
					submit_method:me.submit_method,
					app:me.app,
					slide_type:me.slide_type
				},
				callback: function() {
					if (me.id === me.parent[0].children.length-1) {
						$('.onboarding-dialog').modal('toggle');
						frappe.msgprint({
							message: __('You are all set up!'),
							indicator: 'green',
							title: __('Success')
						});
					}
				},
				onerror: function() {
					me.slides_footer.find('.primary').removeClass('disabled');
				},
				freeze: true
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
				`<a target="_blank" class="small text-muted">${link.label}</a>
				<span class="small">
					<i class="fa fa-question-circle-o" aria-hidden="true"></i>
				</span>`
			);
			if(link.video_id) {
				$link.on('click', () => {
					frappe.help.show_video(link.video_id, link.label);
				})
			}
			this.$help_links.append($link);
		});
	}

	setup_action_button() {
		(this.slide_type !== 'Information') ?
			this.$action_button.addClass('primary') : this.$action_button.removeClass('primary');
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
		this.dialog = new frappe.ui.Dialog({title: __("Let's Onboard!")});
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

		this.$wrapper.find('.modal-title').prepend(
			`<span class="onboarding-icon">
				<i class="fa fa-rocket" aria-hidden="true"></i>
			</span>`
		);
	}

	show() {
		this.dialog.show();
	}
};
