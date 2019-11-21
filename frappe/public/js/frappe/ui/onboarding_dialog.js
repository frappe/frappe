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
		this.$done_state = $(`<div class="text-center">
			<div class="help-links"></div>
		</div>`).appendTo(this.$body);
		if(this.help_links) {
			this.setup_help_links();
		}
	}

	before_show() {
		this.$action_button = this.slides_footer.find('.next-btn')
		if (this.id === 0) {
			this.$action_button.text(__('Start'));
		} else {
			this.$action_button.text(__('Next'));
		} if (this.id === this.parent[0].children.length-1) {
			this.slides_footer.find('.complete-btn').removeClass('hide').addClass('btn-primary action primary');
			this.slides_footer.find('.next-btn').removeClass('action primary');
			this.$action_button = this.slides_footer.find('.complete-btn')
		} else {
			this.slides_footer.find('.complete-btn').removeClass('btn-primary action primary').addClass('hide');
			this.slides_footer.find('.next-btn').addClass('action primary');
			this.$action_button = this.slides_footer.find('.next-btn')
		} if (this.slide_type == 'Action') {
			this.$action_button.addClass('primary');
		} else if (this.slide_type == 'Info') {
			this.$action_button.removeClass('primary');
		}
	}

	primary_action() {
		let me = this;
		if (me.set_values()) {
			me.slides_footer.find('.primary').addClass('disabled');
			frappe.call({
				method: me.submit_method,
				args: {args_data: me.values},
				callback: function() {
					if (me.id === me.parent[0].children.length-1) {
						if (me.slides_footer.find('.complete-btn').hasClass('primary')) {
							$('.user-progress-dialog').modal('toggle');
							frappe.msgprint({
								message: __('You are all set up!'),
								indicator: 'green',
								title: __('Success')
							});
						}
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
		this.slides_footer.find('.action').off('click.primary_action');
	}

	setup_help_links() {
		let $help_links = this.$done_state.find('.help-links');
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
			$help_links.append($link);
		});
		$('.help-links').append($help_links);
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
		this.$wrapper = $(this.dialog.$wrapper).addClass('user-progress-dialog');
		this.slide_container = new frappe.ui.Slides({
			parent: this.dialog.body,
			slides: this.slides,
			slide_class: frappe.setup.OnboardingSlide,
			unidirectional: 1,
			before_load: ($footer) => {
				$footer.find('.prev-btn').addClass('hide');
				$footer.find('.next-btn').removeClass('btn-default').addClass('btn-primary action');
				$footer.find('.text-right').prepend(
					$(`<a class="complete-btn btn btn-sm">
				${__("Complete")}</a>`));
			}
		});

		this.$wrapper.find('.modal-title').prepend(`<span class="onboarding-icon"><i class="fa fa-rocket" aria-hidden="true"></i></span>`);
	}

	show() {
		this.dialog.show();
	}
};
