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
			</div>
			<div class="content-container">
				<h5 class="title"></h5>
				<div class="content"></div>
				<div class="action-area">
					<div class="actions"></div>
					<div class="help-links"></div>
				</div>
				<i class="check pull-right fa fa-fw fa-check-circle text-success"
				style="font-size: 24px;"></i>
			</div>
		</div>`);
		this.property_components = [
			{ card_property: 'content', component_name: '$content', class_name: 'content' },
			{ card_property: 'image', component_name: '$img_container', class_name: 'img-container'},
			{ card_property: 'done', component_name: '$check', class_name: 'check' },
			{ card_property: 'actions', component_name: '$actions', class_name: 'actions' },
			{ card_property: 'help_links', component_name: '$help_links', class_name: 'help-links' },
		];
	}

	setup() {
		this.property_components.map(d => {
			this[d.component_name] = this.container.find('.' + d.class_name);
		});

		if(this.data.video_id) {
			this.data.image = `http://img.youtube.com/vi/${this.data.video_id}/1.jpg`;
			this.$img_container.find('.image-overlay').removeClass('hide');
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
		this.property_components.map(d => {
			if(!this.data[d.card_property]) {
				this[d.component_name].hide();
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
				this.$actions.append($btn);
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
				this.$help_links.append($link);
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
		this.$body.find(".form-wrapper").hide();
		this.$body.find(".slide-help").hide();
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
		} else {
			this.slides_footer.find('.next-btn').removeClass('btn-primary');
		}
	}

	primary_action() {
		var me = this;
		if(this.set_values()) {
			frappe.call({
				method: me.method,
				args: {args_data: me.values},
				callback: function() {
					me.done = 1;
					// hide Create button immediately, or show_slide again
					me.slides_footer.find('.next-btn').addClass('btn-primary');
					me.$primary_btn.hide();
					me.refresh();
				},
				freeze: true
			});
		}
	}

	mark_as_done() {
		// most hard
	}
};

frappe.setup.UserProgressDialog  = class UserProgressDialog {
	constructor({
		slides = []
	}) {
		this.slides = slides;
		// Add a progress bar
		// show the last visited slide
		// Add a mark as done button
		// this.progress_state_dict = this.slides.map();

		this.setup();
	}

	setup() {
		this.dialog = new frappe.ui.Dialog({title: __("Complete Setup")});
		this.slide_container = new frappe.ui.Slides({
			parent: this.dialog.body,
			slides: this.slides,
			slide_class: frappe.setup.UserProgressSlide,
			done_state: 1,
			before_load: ($footer) => {
				$footer.find('.text-right').prepend(
					$(`<a class="make-btn btn btn-primary btn-sm primary">
				${__("Create")}</a>`));
			},
			on_update: (completed, total) => {
				let percent = completed * 100 / total;
				$('.user-progress .progress-bar').css({'width': percent + '%'});
				if(percent === 100) {
					$(document).trigger("user-initial-setup-complete");
				}
			}
		});
		this.make_dismiss_button();
	}

	listen_for_updates() {
		// on every notif 30 sec event
		this.update_progress_state();
	}

	update_progress_state() {
		// update states of slides and cards and refresh them
		// Update the progress bar in both the toolbar and the dialog

		// remove on_update from original slides container
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
		this.$dismiss_button.removeClass('hide');
	}

	show() {
		this.dialog.show();
	}
};
