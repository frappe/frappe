// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("frappe.setup");
frappe.provide("frappe.ui");

frappe.ui.ActionCard = class {
	constructor({
		data = null
	}) {
		this.data = data;
		this.make();
		this.setup();
	}

	make() {
		this.container = $(`<div class="card-container">
			<div class="img-container">
				<img src="" class="clip">
				<div class="image-overlay hide"></div>
				<i class="play fa fa-fw fa-play-circle hide"></i>
			</div>
			<div class="content-container">
				<h5 class="title"></h5>
				<div class="content"></div>
				<div class="action-area"></div>
			</div>
			<i class="check pull-right fa fa-fw fa-check-circle text-success"></i>
		</div>`);
		this.property_components = [
			{ card_properties: ['content'], component_name: '$content', class_name: 'content' },
			{ card_properties: ['image'], component_name: '$img_container', class_name: 'img-container'},
			{ card_properties: ['done'], component_name: '$check', class_name: 'check' },
			{ card_properties: ['actions', 'help_links'], component_name: '$action_area', class_name: 'action-area' }
		];
	}

	setup() {
		this.property_components.map(d => {
			if(!this[d.component_name]) {
				this[d.component_name] = this.container.find('.' + d.class_name);
			}
		});

		if(this.data.video_id) {
			this.data.image = `http://img.youtube.com/vi/${this.data.video_id}/0.jpg`;
			this.$img_container.find('.image-overlay').removeClass('hide');
			this.$img_container.find('.fa-play-circle').removeClass('hide');
		}

		this.refresh();
		if(this.data.video_id) {
			this.bind_single_action(() => {
				frappe.help.show_video(this.data.video_id, this.title);
			});
		}
	}

	refresh() {
		// render according to props
		this.property_components.map(comp => {
			let visible = 0;
			comp.card_properties.map(d => {
				if(this.data[d]) visible = 1;
			});
			if(!visible) {
				this[comp.component_name].hide();
			}
		});

		this.render();
	}

	render() {
		this.container.find('.title').html(this.data.title);
		if(this.data.image) {
			this.$img_container.find('img').attr({"src": this.data.image});
		}
		if(this.data.content) {
			this.$content.html(this.data.content);
		}
		if(this.data.done) {
			this.container.addClass("done");
		}
		if(this.data.actions) {
			this.data.actions.map(action => {
				let $btn = $(`<button class="btn btn-default btn-sm">${action.label}</button>`);
				this.$action_area.append($btn);
				if(action.route) {
					$btn.on('click', () => {
						frappe.set_route(action.route);
					});
				} if(action.new_doc) {
					$btn.on('click', () => {
						frappe.new_doc(action.new_doc);
					});
				}
			});
		}
		if(this.data.help_links) {
			this.data.help_links.map(link => {
				let $link = $(`<a target="_blank" href="${link.url}">${link.label}</a>`);
				this.$action_area.append($link);
			});
		}
	}

	bind_single_action(onclick) {
		if(this.data.video_id) {
			// on entire card click
			this.container.on('mouseenter', () => {
				this.container.addClass('single_action');
			}).on('mouseleave', () => {
				this.container.removeClass('single_action');
			}).on('click', onclick);
		}
	}

	mark_as_done() {}

}

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
		this.make_action_cards();
	}

	make_action_cards() {
		this.$done_state = $(`<div class="done-content">
			<div class="actions cards-container">

			</div>
		</div>`).appendTo(this.$body);

		this.$actions = this.$done_state.find('.actions');
		this.action_cards.map(this.add_card.bind(this));
	}

	add_card(data) {
		let card = new frappe.ui.ActionCard({
			data: data
		});

		card.container.appendTo(this.$actions);
	}

	before_show() {
		if(this.done) {
			this.slides_footer.find('.next-btn').addClass('btn-primary');
			this.slides_footer.find('.done-btn').hide();
		} else {
			this.slides_footer.find('.next-btn').removeClass('btn-primary');
			this.slides_footer.find('.done-btn').show();
		}
	}

	primary_action() {
		var me = this;
		if(this.set_values()) {
			frappe.call({
				method: me.submit_method,
				args: {args_data: me.values},
				callback: function() {
					me.done = 1;
					me.refresh();
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
		this.$progress = $(`<div class="progress-chart">
			<div class="progress"><div class="progress-bar"></div></div>
		</div>`);
		this.dialog.header.find('.col-xs-7').append(this.$progress);
		this.slide_container = new frappe.ui.Slides({
			parent: this.dialog.body,
			slides: this.slides,
			slide_class: frappe.setup.UserProgressSlide,
			done_state: 1,
			before_load: ($footer) => {
				$footer.find('.text-right')
					.prepend($(`<a class="done-btn btn btn-default btn-sm">
					${__("Mark as Done")}</a>`))
					.prepend($(`<a class="make-btn btn btn-primary btn-sm primary">
					${__("Create")}</a>`));
			},
			on_update: (completed, total) => {
				let percent = completed * 100 / total;
				this.$wrapper.find('.progress-bar').css({'width': percent + '%'});
				$('.user-progress .progress-bar').css({'width': percent + '%'});
				if(percent === 100) {
					$(document).trigger("user-initial-setup-complete");
				}
			}
		});

		this.$wrapper.find('.done-btn').on('click', () => {
			this.mark_as_done();
		});

		this.make_dismiss_button();
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
				// console.log("states", r.message);
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
		this.update_progress_bars();
	}

	update_progress_bars() {
		this.$wrapper.find('.progress-bar').css({'width': this.progress_percent + '%'});
		$('.user-progress .progress-bar').css({'width': this.progress_percent + '%'});
		if(this.progress_percent === 100) {
			$(document).trigger("user-initial-setup-complete");
		}
	}

	make_dismiss_button() {
		this.dialog.set_primary_action(__('Dismiss'), () => {
			$('.user-progress').addClass('hide');
			this.dialog.hide();
		});
		this.$dismiss_button = this.dialog.header.find('.btn-primary').addClass('dismiss-btn');
		// hidden by default
		this.$dismiss_button.addClass('hide');

		$(document).on("user-initial-setup-complete", () => {
			this.add_finish_slide_and_make_dismissable();
		});
	}

	add_finish_slide_and_make_dismissable() {
		clearInterval(this.updater);
		this.$dismiss_button.removeClass('hide');
	}

	show() {
		this.dialog.show();
	}
};
