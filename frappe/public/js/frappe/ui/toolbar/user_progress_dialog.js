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
		this.$body.find(".form-wrapper").hide();

		this.make_done_state();
		this.bind_done_state();
	}

	make_done_state() {
		this.$done_state = $(`<div class="done-content">
			<div class="state text-center">
				<p><i class="octicon octicon-check text-success" style="font-size: 30px;"></i></p>
				<p style="font-size: 16px;">${__("Completed!")}</p>
			</div>
			<div class="actions">
				<div class="doctype-actions text-center hide">
					<a class="list-btn btn btn-default btn-sm"></a>
					<a class="sec-list-btn btn btn-default btn-sm hide"></a>
					<a class="import-btn btn btn-default btn-sm"></a>
				</div>
				<div class="doc-actions text-center hide">
					<a class="doc-btn btn btn-default btn-sm">${__("Check it out")}</a>
				</div>
				<div class="next-steps-links">
					<h6 class="title">${__("Going Further")}</h6>
					<a>${__("help link")}</a>
				</div>
			</div>
		</div>`).appendTo(this.$body);
	}

	bind_done_state() {
		if(this.doctype) {
			this.$body.find('.doctype-actions').removeClass("hide");
			this.$list = this.$body.find('.list-btn')
				.html("Go to " + this.name)
				.on('click', () => {
					frappe.set_route("List", this.doctype);
				});
			if(this.sec_doctype) {
				this.$sec_list = this.$body.find('.sec-list-btn')
					.removeClass("hide")
					.html("Go to " + this.sec_doctype + "s")
					.on('click', () => {
						frappe.set_route("List", this.sec_doctype);
					});
			}
			this.$import = this.$body.find('.import-btn')
				.html("Import " + this.name)
				.on('click', () => {
					frappe.set_route("data-import-tool");
				});
		} else if (this.route) {
			this.$body.find('.doc-actions').removeClass("hide");
			this.$doc = this.$body.find('.doc-btn').on('click', () => {
				frappe.set_route(this.route);
			});
		}
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
};

frappe.setup.UserProgressDialog  = class UserProgressDialog {
	constructor({
		slides = []
	}) {
		this.slides = slides;
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

	make_dismiss_button() {
		this.dialog.set_primary_action(__('Dismiss'), () => {
			$('.user-progress').addClass('hide');
			this.dialog.hide();
		});
		this.$dismiss_button = this.dialog.header.find('.btn-primary').addClass('dismiss-btn');
		// hidden by default
		this.$dismiss_button.addClass('hide');

		$(document).on("user-initial-setup-complete", () => {
			this.show_dismiss_button();
		});
	}

	show_dismiss_button() {
		this.$dismiss_button.removeClass('hide');
	}

	show() {
		this.dialog.show();
	}
};
