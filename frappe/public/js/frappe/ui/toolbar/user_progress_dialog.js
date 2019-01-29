// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("frappe.setup");
frappe.provide("frappe.ui");

frappe.setup.UserProgressSlide = class UserProgressSlide extends frappe.ui.Slide {
	constructor(slide = null) {
		super(slide);
	}

	make() {
		super.make();
	}

	setup_done_state() {
		this.$body.find(".slide-help").hide();
		this.$body.find(".form-wrapper").hide();
		this.slides_footer.find('.next-btn').addClass('btn-primary');
		this.slides_footer.find('.done-btn').hide();
		this.$primary_btn.hide();
		this.make_done_state();
	}

	make_done_state() {
		this.$done_state = $(`<div class="done-state text-center">
			<div class="check-container"><i class="check fa fa-fw fa-check-circle text-success"></i></div>
			<h4 class="title"><a></a></h4>
			<div class="help-links"></div>
		</div>`).appendTo(this.$body);

		this.$done_state_title = this.$done_state.find('.title');
		this.$check = this.$done_state.find('.check');
		this.$help_links = this.$done_state.find('.help-links');

		if(this.done_state_title) {
			$("<a>" + this.done_state_title + "</a>").appendTo(this.$done_state_title);
			this.$done_state_title.on('click', () => {
				frappe.set_route(this.done_state_title_route);
			});
		}

		if(this.help_links) {
			this.help_links.map(link => {
				let $link = $(`<a target="_blank" class="small text-muted">${link.label}</a>`);
				if(link.url) {
					$link.attr({"href": link.url});
				} else if(link.video_id) {
					$link.on('click', () => {
						frappe.help.show_video(link.video_id, link.label);
					})
				}
				this.$help_links.append($link);
			});
		}

	}

	before_show() {
		if(this.done) {
			this.slides_footer.find('.next-btn').addClass('btn-primary');
			this.slides_footer.find('.done-btn').hide();
		} else {
			this.slides_footer.find('.next-btn').removeClass('btn-primary');
			this.slides_footer.find('.done-btn').show();
		}
		if(this.dialog_dismissed) {
			this.slides_footer.find('.next-btn').removeClass('btn-primary');
		}
	}

	primary_action() {
		var me = this;
		if(this.set_values()) {
			this.slides_footer.find('.make-btn').addClass('disabled');
			frappe.call({
				method: me.submit_method,
				args: {args_data: me.values},
				callback: function() {
					me.done = 1;
					me.refresh();
				},
				onerror: function() {
					me.slides_footer.find('.make-btn').removeClass('disabled');
				},
				freeze: true
			});
		}
	}
};

frappe.setup.UserProgressDialog  = class UserProgressDialog {
	constructor({
		slides = []
	}) {
		this.slides = slides;
		this.progress_state_dict = {};
		this.slides.map(slide => {
			this.progress_state_dict[slide.action_name] = slide.done || 0;
		});
		this.progress_percent = 0;
		this.setup();
	}

	setup() {
		this.dialog = new frappe.ui.Dialog({title: __("Complete Setup")});
		this.$wrapper = $(this.dialog.$wrapper).addClass('user-progress-dialog');
		this.slide_container = new frappe.ui.Slides({
			parent: this.dialog.body,
			slides: this.slides,
			slide_class: frappe.setup.UserProgressSlide,
			done_state: 1,
			before_load: ($footer) => {
				$footer.find('.text-right')
					.prepend($(`<a class="done-btn btn btn-default btn-sm">
					${__("Mark as Done")}</a>`))
					.append($(`<a class="make-btn btn btn-primary btn-sm primary action">
					${__("Create")}</a>`));
			},
			on_update: (completed, total) => {
				let percent = completed * 100 / total;
				$('.user-progress .progress-bar').css({'width': percent + '%'});
				if(percent === 100) {
					this.dismiss_progress();
				}
			}
		});

		this.$wrapper.find('.done-btn').on('click', () => {
			this.mark_as_done();
		});

		this.get_and_update_progress_state();
		this.check_for_updates();
	}

	mark_as_done() {
		let me = this;
		let current_slide = this.slide_container.current_slide;
		frappe.call({
			method: current_slide.mark_as_done_method,
			args: {action_name: current_slide.action_name},
			callback: function() {
				current_slide.done = 1;
				current_slide.refresh();
			},
			freeze: true
		});
	}

	check_for_updates() {
		this.updater = setInterval(() => {
			this.get_and_update_progress_state();
		}, 60000);
	}

	get_and_update_progress_state() {
		var me = this;
		frappe.call({
			method: "frappe.desk.user_progress.update_and_get_user_progress",
			callback: function(r) {
				let states = r.message;
				let changed = 0;
				let completed = 0;
				Object.keys(states).map(action_name => {
					if(states[action_name]) {
						completed ++;
					}
					if(me.progress_state_dict[action_name] != states[action_name]) {
						changed = 1;
						me.progress_state_dict[action_name] = states[action_name];
					}
				});

				if(changed) {
					Object.keys(me.slide_container.slide_dict).map((id) => {
						let slide = me.slide_container.slide_dict[id];
						if(me.progress_state_dict[slide.action_name]) {
							if(!slide.done) {
								slide.done = 1;
								slide.refresh();
							}
						}
					});

				}
				me.progress_percent = completed / Object.keys(states).length * 100;
				me.update_progress();
			},
			freeze: false
		});
	}

	update_progress() {
		$('.user-progress .progress-bar').css({'width': this.progress_percent + '%'});
		if(this.progress_percent === 100) {
			this.dismiss_progress();
		}
	}

	dismiss_progress() {
		$('.user-progress').addClass('hide');
		clearInterval(this.updater);
	}

	show() {
		this.dialog.show();
	}
};
