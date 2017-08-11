// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("frappe.setup");

frappe.setup.ProgressSlide = class ProgressSlide {
	constructor(slide = null) {
		$.extend(this, slide);
		this.setup();
	}
	setup() {
		this.$wrapper = $('<div class="slide-wrapper hidden"></div>')
			.appendTo(this.parent)
			.attr("data-slide-id", this.id);
	}
	make() {
		if(this.$body) this.$body.remove();

		if(this.before_load) {
			this.before_load(this);
		}
		this.$body = $(frappe.render_template("user_progress_slide", {
			help: __(this.help),
			title:__(this.title),
			image_src: __(this.image_src),
			step: this.id,
			name: this.name,
			slides_count: this.container.slides.length,
			success_states: this.container.slides.map((slide, i) => {
				if(this.container.slide_dict[i]) {
					return this.container.slide_dict[i].done || 0;
				} else {
					return slide.done || 0;
				}
			})
		})).appendTo(this.$wrapper);

		this.make_progress_dots();
		this.make_prev_next_buttons();

		if(!this.done) {
			this.$make = this.$body.find('.make-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(this.make_records.bind(this));
			this.setup_form();
		} else {
			this.setup_success_state();
		}
	}
	setup_success_state() {
		this.$success_state = this.$body.find(".success-state").removeClass("hide");
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
	setup_form() {
		this.$form = this.$body.find(".form").removeClass("hide");
		var fields = JSON.parse(JSON.stringify(this.fields));
		if(this.add_more) {
			this.count = 1;
			fields = fields.map((field, i) => {
				if(field.fieldname) {
					field.fieldname += '_1';
				}
				if(i === 1 && this.mandatory_entry) {
					field.reqd = 1;
				}
				if(!field.static) {
					if(field.label) field.label += ' 1';
				}
				return field;
			});
		}
		if(this.fields) {
			this.form = new frappe.ui.FieldGroup({
				fields: fields,
				body: this.$form[0],
				no_submit_on_enter: true
			});
			this.form.make();
		} else {
			this.$form.html(this.html);
		}

		this.set_reqd_fields();

		if(this.add_more) this.bind_more_button();
		var $primary_btn = this.$make;
		this.bind_fields_to_make($primary_btn);

		if(this.onload) {
			this.onload(this);
		}
		this.set_reqd_fields();
		this.bind_fields_to_make($primary_btn);
		this.reset_make($primary_btn);
		setTimeout(function() {
			this.$body.find('.form-control').first().focus();
		}.bind(this), 0);
	}
	make_progress_dots() {
		var me = this;
		this.$body.find('.fa-circle').on('click', function() {
			let id = $(this).attr('data-step-id');
			me.change_slide(id);
		});
	}
	make_prev_next_buttons() {
		if(this.id > 0) {
			this.$prev = this.$body.find('.prev-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.on('click', () => { this.change_slide(this.id - 1); });
		}
		if(this.id+1 < this.container.slides.length) {
			this.$next = this.$body.find('.next-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.on('click', () => { this.change_slide(this.id + 1); });
		}
	}
	change_slide(id) {
		this.container.show_slide(id);
	}

	// Form methods
	set_reqd_fields() {
		var dict = this.form.fields_dict;
		this.reqd_fields = [];
		Object.keys(dict).map(key => {
			if(dict[key].df.reqd) {
				this.reqd_fields.push(dict[key]);
			}
		});
	}
	set_values() {
		this.values = this.form.get_values();
		if(this.values===null) {
			return false;
		}
		if(this.validate && !this.validate()) {
			return false;
		}
		return true;
	}
	bind_more_button() {
		this.$more = this.$body.find('.more-btn');
		this.$more.removeClass('hide')
			.on('click', () => {
				this.count++;
				var fields = JSON.parse(JSON.stringify(this.fields));
				this.form.add_fields(fields.map(field => {
					if(field.fieldname) field.fieldname += '_' + this.count;
					if(!field.static) {
						if(field.label) field.label += ' ' + this.count;
					}
					return field;
				}));
				if(this.count === this.max_count) {
					this.$more.addClass('hide');
				}
			});
	}
	bind_fields_to_make($primary_btn) {
		var me = this;
		this.reqd_fields.map((field) => {
			field.$wrapper.on('change input', () => {
				me.reset_make($primary_btn);
			});
		});
	}
	reset_make($primary_btn) {
		var empty_fields = this.reqd_fields.filter((field) => {
			return !field.get_value();
		});
		if(empty_fields.length) {
			$primary_btn.addClass('disabled');
		} else {
			$primary_btn.removeClass('disabled');
		}
	}

	// Primary button action
	make_records() {
		var me = this;
		if(this.set_values()) {
			frappe.call({
				method: me.method,
				args: {args_data: me.form.get_values()},
				callback: function() {
					me.done = 1;
					me.make();
					let completed = 0;
					me.container.slides.map((slide, i) => {
						if(me.container.slide_dict[i]) {
							if(me.container.slide_dict[i].done) completed++;
						} else {
							if(slide.done) completed++;
						}
					});
					let percent = completed * 100 / me.container.slides.length;
					$('.user-progress .progress-bar').css({'width': percent + '%'});
					if(percent === 100) {
						$(document).trigger("user-initial-setup-complete");
					}
				},
				freeze: true
			});
		}
	}
};

frappe.setup.Slides = class Slides {
	constructor({
		parent = null,
		slides = [],
		slide_class = null
	}) {
		this.parent = parent;
		this.slides = slides;
		this.slide_class = slide_class;
		this.setup();
	}
	setup() {
		this.container = $('<div>').addClass("slide-container").appendTo(this.parent);
		this.slide_dict = {};
		this.slides.map((slide, id) => {
			if(!this.slide_dict[id]) {
				this.slide_dict[id] = new (this.slide_class)(
					$.extend(this.slides[id], {
						container: this,
						parent: this.container,
						id: id})
				);
				this.slide_dict[id].make();
			}
		});
		this.show_slide(0);
	}
	show_slide(id) {
		this.slide_dict[id].make();
		this.hide_current_slide();
		this.current_slide = this.slide_dict[id];
		this.current_slide.$wrapper.removeClass("hidden");
	}

	hide_current_slide() {
		if(this.current_slide) {
			this.current_slide.$wrapper.addClass("hidden");
			this.current_slide = null;
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
		this.slide_container = new frappe.setup.Slides({
			parent: this.dialog.body,
			slides: this.slides,
			slide_class: frappe.setup.ProgressSlide
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