frappe.provide("frappe.setup");

frappe.setup.ProgressSlide = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.$wrapper = $('<div class="slide-wrapper hidden"></div>')
			.appendTo(this.dialog.d.body)
			.attr("data-slide-id", this.id);
	},
	make: function() {
		var me = this;
		if(this.$body) this.$body.remove();

		if(this.before_load) {
			this.before_load(this);
		}
		this.$body = $(frappe.render_template("user_progress_slide", {
			help: __(this.help),
			title:__(this.title),
			image_src: __(this.image_src),
			main_title:__(this.dialog.title),
			step: this.id + 1,
			name: this.name,
			slides_count: this.dialog.slides.length,
			success_states: this.dialog.slides.map((slide, i) => {
				if(this.dialog.slide_dict[i]) {
					return this.dialog.slide_dict[i].done || 0;
				} else {
					return slide.done || 0;
				}
			})
		})).appendTo(this.$wrapper);

		this.make_prev_next_buttons();

		this.content = this.$body.find(".form")[0];
		if(!this.done) {
			this.$make = this.$body.find('.make-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(this.make_records.bind(this));
			this.setup_form();
		} else {
			this.setup_success_state();
		}
	},
	setup_success_state: function() {
		console.log(this);
		this.$success_state = this.$body.find(".success-state").removeClass("hide");
		if(this.doctype) {
			this.$body.find('.doctype-actions').removeClass("hide");
			this.$list = this.$body.find('.list-btn').on('click', () => {
				frappe.set_route("List", this.doctype);
			});
		} else if (this.route) {
			this.$body.find('.doc-actions').removeClass("hide");
			this.$doc = this.$body.find('.doc-btn').on('click', () => {
				frappe.set_route(this.route);
			});
		}
	},
	setup_form: function() {
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
				body: this.content,
				no_submit_on_enter: true
			});
			this.form.make();
		} else {
			$(this.content).html(this.html);
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
		this.focus_first_input();
	},
	set_reqd_fields: function() {
		var dict = this.form.fields_dict;
		this.reqd_fields = [];
		Object.keys(dict).map(key => {
			if(dict[key].df.reqd) {
				this.reqd_fields.push(dict[key]);
			}
		});
	},
	set_values: function() {
		this.values = this.form.get_values();
		if(this.values===null) {
			return false;
		}
		if(this.validate && !this.validate()) {
			return false;
		}
		return true;
	},
	bind_more_button: function() {
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
	},
	make_prev_next_buttons: function() {
		if(this.id > 0) {
			this.$prev = this.$body.find('.prev-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(() => { this.prev(); })
				.css({"margin-right": "10px"});
		}
		if(this.id+1 < this.dialog.slides.length) {
			this.$next = this.$body.find('.next-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(this.next.bind(this));
		}
	},
	bind_fields_to_make: function($primary_btn) {
		var me = this;
		this.reqd_fields.map((field) => {
			field.$wrapper.on('change input', () => {
				me.reset_make($primary_btn);
			});
		});
	},
	reset_make: function($primary_btn) {
		var empty_fields = this.reqd_fields.filter((field) => {
			return !field.get_value();
		});
		if(empty_fields.length) {
			$primary_btn.addClass('disabled');
		} else {
			$primary_btn.removeClass('disabled');
		}
	},
	focus_first_input: function() {
		setTimeout(function() {
			this.$body.find('.form-control').first().focus();
		}.bind(this), 0);
	},
	make_records: function() {
		var me = this;
		if(this.set_values()) {
			frappe.call({
				method: me.method,
				args: {args_data: me.form.get_values()},
				callback: function(r) {
					me.done = 1;
					me.make();
					let completed = 0;
					me.dialog.slides.map((slide, i) => {
						if(me.dialog.slide_dict[i]) {
							if(me.dialog.slide_dict[i].done) completed++;
						} else {
							if(slide.done) completed++;
						}
					})
					let percent = completed * 100 / me.dialog.slides.length;
					$('.user-progress .progress-bar').css({'width': percent + '%'});
				},
				freeze: true
			});
		}
	},
	next: function() {
		this.dialog.show_slide(this.id + 1);
	},
	prev: function() {
		this.dialog.show_slide(this.id - 1);
	}
});

frappe.setup.UserProgressDialog  = class UserProgressDialog {
	constructor({
		slides = []
	}) {
		this.slides = slides;
		this.setup();
	}

	setup() {
		this.d = new frappe.ui.Dialog({title: __("Setup Tour")});
		this.slide_dict = {};
		this.slides.map((slide, id) => {
			if(!this.slide_dict[id]) {
				this.slide_dict[id] = new frappe.setup.ProgressSlide(
					$.extend(this.slides[id], {dialog: this, id:id})
				);
				this.slide_dict[id].make();
			}
		});
		this.show_slide(0);
	}

	show() {
		// Calculate the progress number and render bar
		// render slide states
		this.d.show();
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