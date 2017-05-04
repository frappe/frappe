frappe.provide("frappe.wiz");
frappe.provide("frappe.wiz.events");

frappe.wiz = {
	slides: [],
	events: {},
	remove_app_slides: [],
	on: function(event, fn) {
		if(!frappe.wiz.events[event]) {
			frappe.wiz.events[event] = [];
		}
		frappe.wiz.events[event].push(fn);
	},
	add_slide: function(slide) {
		frappe.wiz.slides.push(slide);
	},

	run_event: function(event) {
		$.each(frappe.wiz.events[event] || [], function(i, fn) {
			fn();
		});
	}
}

frappe.pages['setup-wizard'].on_page_load = function(wrapper) {
	// setup page ui
	$(".navbar:first").toggle(false);
	$("body").css({"padding-top":"30px"});

	var requires = ["/assets/frappe/css/animate.min.css"].concat(frappe.boot.setup_wizard_requires || []);

	frappe.require(requires, function() {
		frappe.wiz.run_event("before_load");
		var wizard_settings = {
			page_name: "setup-wizard",
			parent: wrapper,
			slides: frappe.wiz.slides,
			title: __("Welcome")
		}

		frappe.wizard = new frappe.wiz.Wizard(wizard_settings);
		frappe.wiz.run_event("after_load");

		// frappe.wizard.values = test_values_edu;

		var route = frappe.get_route();
		if(route) {
			frappe.wizard.show(route[1]);
		}
	});
}

frappe.pages['setup-wizard'].on_page_show = function(wrapper) {
	if(frappe.get_route()[1]) {
		frappe.wizard && frappe.wizard.show(frappe.get_route()[1]);
	}
}

frappe.wiz.Wizard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.slides;
		this.slide_dict = {};
		this.values = {};
		this.welcomed = true;
		frappe.set_route("setup-wizard/0");
	},
	make: function() {
		this.parent = $('<div class="setup-wizard-wrapper">').appendTo(this.parent);
	},
	get_message: function(html) {
		return $(repl('<div data-state="setup-complete">\
			<div style="padding: 40px;" class="text-center">%(html)s</div>\
		</div>', {html:html}))
	},
	show_working: function() {
		this.hide_current_slide();
		frappe.set_route(this.page_name);
		this.current_slide = {"$wrapper": this.get_message(this.working_html()).appendTo(this.parent)};
	},
	show_complete: function() {
		this.hide_current_slide();
		this.current_slide = {"$wrapper": this.get_message(this.complete_html()).appendTo(this.parent)};
	},
	show: function(id) {
		if(!this.welcomed) {
			frappe.set_route(this.page_name);
			return;
		}
		id = cint(id);
		if(this.current_slide && this.current_slide.id===id) {
			return;
		}

		this.update_values();

		if(!this.slide_dict[id]) {
			this.slide_dict[id] = new frappe.wiz.WizardSlide($.extend(this.slides[id], {wiz:this, id:id}));
			this.slide_dict[id].make();
		}

		this.hide_current_slide();

		this.current_slide = this.slide_dict[id];
		this.current_slide.$wrapper.removeClass("hidden");
	},
	hide_current_slide: function() {
		if(this.current_slide) {
			this.current_slide.$wrapper.addClass("hidden");
			this.current_slide = null;
		}
	},
	get_values: function() {
		var values = {};
		$.each(this.slide_dict, function(id, slide) {
			if(slide.values) {
				$.extend(values, slide.values);
			}
		});
		return values;
	},
	working_html: function() {
		var msg = $(frappe.render_template("setup_wizard_message", {
			image: "/assets/frappe/images/ui/bubble-tea-smile.svg",
			title: __("Setting Up"),
			message: __('Sit tight while your system is being setup. This may take a few moments.')
		}));
		msg.find(".setup-wizard-message-image").addClass("animated infinite bounce");
		return msg.html();
	},

	complete_html: function() {
		return frappe.render_template("setup_wizard_message", {
			image: "/assets/frappe/images/ui/bubble-tea-happy.svg",
			title: __('Setup Complete'),
			message: ""
		});
	},

	on_complete: function() {
		var me = this;
		this.update_values();
		this.show_working();
		return frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
			args: {args: this.values},
			callback: function(r) {
				me.show_complete();
				if(frappe.wiz.welcome_page) {
					localStorage.setItem("session_last_route", frappe.wiz.welcome_page);
				}
				setTimeout(function() {
					window.location = "/desk";
				}, 2000);
			},
			error: function(r) {
				var d = msgprint(__("There were errors."));
				d.custom_onhide = function() {
					frappe.set_route(me.page_name, me.slides.length - 1);
				};
			}
		});
	},

	update_values: function() {
		this.values = $.extend(this.values, this.get_values());
	},

	refresh_slides: function() {
		// reset all slides so that labels are translated
		var me = this;
		if(this.in_refresh_slides) {
			return;
		}
		this.in_refresh_slides = true;

		if(!this.current_slide.set_values()) {
			return;
		}

		this.update_values();

		frappe.wiz.slides = [];
		frappe.wiz.run_event("before_load");

		// remove slides listed in remove_app_slides
		var new_slides = [];
		frappe.wiz.slides.forEach(function(slide) {
			if(frappe.wiz.domain) {
				var domains = slide.domains;
				if (domains.indexOf('all') !== -1 ||
					domains.indexOf(frappe.wiz.domain.toLowerCase()) !== -1) {
					new_slides.push(slide);
				}
			} else {
				new_slides.push(slide);
			}
		})
		frappe.wiz.slides = new_slides;

		this.slides = frappe.wiz.slides;
		frappe.wiz.run_event("after_load");

		// re-render all slides
		this.slide_dict = {};

		var current_id = this.current_slide.id;
		this.current_slide.destroy();

		this.show(current_id);
		this.in_refresh_slides = false;
	}
});

frappe.wiz.WizardSlide = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.$wrapper = $('<div class="slide-wrapper hidden"></div>')
			.appendTo(this.wiz.parent)
			.attr("data-slide-id", this.id);
	},
	make: function() {
		var me = this;
		if(this.$body) this.$body.remove();

		if(this.before_load) {
			this.before_load(this);
		}

		this.$body = $(frappe.render_template("setup_wizard_page", {
				help: __(this.help),
				title:__(this.title),
				main_title:__(this.wiz.title),
				step: this.id + 1,
				name: this.name,
				css_class: this.css_class || "",
				slides_count: this.wiz.slides.length
			})).appendTo(this.$wrapper);

		this.body = this.$body.find(".form")[0];

		if(this.fields) {
			this.form = new frappe.ui.FieldGroup({
				fields: this.fields,
				body: this.body,
				no_submit_on_enter: true
			});
			this.form.make();
		} else {
			$(this.body).html(this.html);
		}

		this.set_init_values();
		this.make_prev_next_buttons();

		if(this.onload) {
			this.onload(this);
		}
		this.focus_first_input();

	},
	set_init_values: function() {
		var me = this;
		// set values from frappe.wiz.values
		if(frappe.wizard.values && this.fields) {
			this.fields.forEach(function(f) {
				var value = frappe.wizard.values[f.fieldname];
				if(value) {
					me.get_field(f.fieldname).set_input(value);
				}
			});
		}
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

	make_prev_next_buttons: function() {
		var me = this;

		// prev
		if(this.id > 0) {
			this.$prev = this.$body.find('.prev-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(function() {
					me.prev();
				})
				.css({"margin-right": "10px"});
		}

		// next or complete
		if(this.id+1 < this.wiz.slides.length) {
			this.$next = this.$body.find('.next-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(this.next_or_complete.bind(this));
		} else {
			this.$complete = this.$body.find('.complete-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(this.next_or_complete.bind(this));
		}

		//setup mousefree navigation
		this.$body.on('keypress', function(e) {
			if(e.which === 13) {
				$target = $(e.target);
				if($target.hasClass('prev-btn')) {
					me.prev();
				} else if($target.hasClass('btn-attach')) {
					//do nothing
				} else {
					me.next_or_complete();
					e.preventDefault();
				}
			}
		});
	},
	next_or_complete: function() {
		if(this.set_values()) {
			if(this.id+1 < this.wiz.slides.length) {
				this.next();
			} else {
				this.wiz.on_complete(this.wiz);
			}
		}
	},
	focus_first_input: function() {
		setTimeout(function() {
			this.$body.find('.form-control').first().focus();
		}.bind(this), 0);
	},
	next: function() {
		frappe.set_route(this.wiz.page_name, this.id+1 + "");
	},
	prev: function() {
		frappe.set_route(this.wiz.page_name, this.id-1 + "");
	},
	get_input: function(fn) {
		return this.form.get_input(fn);
	},
	get_field: function(fn) {
		return this.form.get_field(fn);
	},
	destroy: function() {
		this.$body.remove();
		if(frappe.wizard.current_slide===this) {
			frappe.wizard.current_slide = null;
		}
	},
});

function load_frappe_slides() {
	// language selection
	frappe.wiz.welcome = {
		name: "welcome",
		domains: ["all"],
		title: __("Welcome"),
		icon: "fa fa-world",
		help: __("Let's prepare the system for first use."),

		fields: [
			{ fieldname: "language", label: __("Select Your Language"), reqd:1,
				fieldtype: "Select", "default": "english" },
		],

		onload: function(slide) {
			if (!frappe.wiz.welcome.data) {
				frappe.wiz.welcome.load_languages(slide);
			} else {
				frappe.wiz.welcome.setup_fields(slide);
			}
		},

		css_class: "single-column",
		load_languages: function(slide) {
			frappe.call({
				method: "frappe.desk.page.setup_wizard.setup_wizard.load_languages",
				freeze: true,
				callback: function(r) {
					frappe.wiz.welcome.data = r.message;
					frappe.wiz.welcome.setup_fields(slide);

					var language_field = slide.get_field("language");
					language_field.set_input(frappe.wiz.welcome.data.default_language || "english");

					if (!frappe.wiz._from_load_messages) {
						language_field.$input.trigger("change");
					}

					delete frappe.wiz._from_load_messages;

					moment.locale("en");
				}
			});
		},

		setup_fields: function(slide) {
			var select = slide.get_field("language");
			select.df.options = frappe.wiz.welcome.data.languages;
			select.refresh();
			frappe.wiz.welcome.bind_events(slide);
		},

		bind_events: function(slide) {
			slide.get_input("language").unbind("change").on("change", function() {
				var lang = $(this).val() || "english";
				frappe._messages = {};
				frappe.call({
					method: "frappe.desk.page.setup_wizard.setup_wizard.load_messages",
					freeze: true,
					args: {
						language: lang
					},
					callback: function(r) {
						frappe.wiz._from_load_messages = true;
						frappe.wizard.refresh_slides();
					}
				});
			});
		}
	},

	// region selection
	frappe.wiz.region = {
		domains: ["all"],
		title: __("Region"),
		icon: "fa fa-flag",
		help: __("Select your Country, Time Zone and Currency"),
		fields: [
			{ fieldname: "country", label: __("Country"), reqd:1,
				fieldtype: "Select" },
			{ fieldname: "timezone", label: __("Time Zone"), reqd:1,
				fieldtype: "Select" },
			{ fieldname: "currency", label: __("Currency"), reqd:1,
				fieldtype: "Select" },
		],

		onload: function(slide) {
			var _setup = function() {
				frappe.wiz.region.setup_fields(slide);
				frappe.wiz.region.bind_events(slide);
			};

			if(frappe.wiz.regional_data) {
				_setup();
			} else {
				frappe.call({
					method:"frappe.geo.country_info.get_country_timezone_info",
					callback: function(data) {
						frappe.wiz.regional_data = data.message;
						_setup();
					}
				});
			}
		},
		css_class: "single-column",
		setup_fields: function(slide) {
			var data = frappe.wiz.regional_data;

			slide.get_input("country").empty()
				.add_options([""].concat(keys(data.country_info).sort()));


			slide.get_input("currency").empty()
				.add_options(frappe.utils.unique([""].concat($.map(data.country_info,
					function(opts, country) { return opts.currency; }))).sort());

			slide.get_input("timezone").empty()
				.add_options([""].concat(data.all_timezones));

			// set values if present
			if(frappe.wizard.values.country) {
				slide.get_field("country").set_input(frappe.wizard.values.country);
			} else if (data.default_country) {
				slide.get_field("country").set_input(data.default_country);
			}

			if(frappe.wizard.values.currency) {
				slide.get_field("currency").set_input(frappe.wizard.values.currency);
			}

			if(frappe.wizard.values.timezone) {
				slide.get_field("timezone").set_input(frappe.wizard.values.timezone);
			}

		},

		bind_events: function(slide) {
			slide.get_input("country").on("change", function() {
				var country = slide.get_input("country").val();
				var $timezone = slide.get_input("timezone");
				var data = frappe.wiz.regional_data;

				$timezone.empty();

				// add country specific timezones first
				if(country) {
					var timezone_list = data.country_info[country].timezones || [];
					$timezone.add_options(timezone_list.sort());
					slide.get_field("currency").set_input(data.country_info[country].currency);
					slide.get_field("currency").$input.trigger("change");
				}

				// add all timezones at the end, so that user has the option to change it to any timezone
				$timezone.add_options([""].concat(data.all_timezones));

				slide.get_field("timezone").set_input($timezone.val());

				// temporarily set date format
				frappe.boot.sysdefaults.date_format = (data.country_info[country].date_format
					|| "dd-mm-yyyy");
			});

			slide.get_input("currency").on("change", function() {
				var currency = slide.get_input("currency").val();
				if (!currency) return;
				frappe.model.with_doc("Currency", currency, function() {
					frappe.provide("locals.:Currency." + currency);
					var currency_doc = frappe.model.get_doc("Currency", currency);
					var number_format = currency_doc.number_format;
					if (number_format==="#.###") {
						number_format = "#.###,##";
					} else if (number_format==="#,###") {
						number_format = "#,###.##"
					}

					frappe.boot.sysdefaults.number_format = number_format;
					locals[":Currency"][currency] = $.extend({}, currency_doc);
				});
			});
		}
	},


	frappe.wiz.user = {
		domains: ["all"],
		title: __("The First User: You"),
		icon: "fa fa-user",
		fields: [
			{"fieldname": "full_name", "label": __("Full Name"), "fieldtype": "Data",
				reqd:1},
			{"fieldname": "email", "label": __("Email Address"), "fieldtype": "Data",
				reqd:1, "description": __("Login id"), "options":"Email"},
			{"fieldname": "password", "label": __("Password"), "fieldtype": "Password",
				reqd:1},
			{fieldtype:"Attach Image", fieldname:"attach_user",
				label: __("Attach Your Picture"), is_private: 0},
		],
		help: __('The first user will become the System Manager (you can change this later).'),
		onload: function(slide) {
			if(user!=="Administrator") {
				slide.form.fields_dict.password.$wrapper.toggle(false);
				slide.form.fields_dict.email.$wrapper.toggle(false);
				if(frappe.boot.user.first_name || frappe.boot.user.last_name) {
					slide.form.fields_dict.full_name.set_input(
						[frappe.boot.user.first_name, frappe.boot.user.last_name].join(' ').trim());
				}

				var user_image = frappe.get_cookie("user_image");
				if(user_image) {
					var $attach_user = slide.form.fields_dict.attach_user.$wrapper;
					$attach_user.find(".missing-image").toggle(false);
					$attach_user.find("img").attr("src", decodeURIComponent(user_image)).toggle(true);
				}

				delete slide.form.fields_dict.email;
				delete slide.form.fields_dict.password;
			}
		},
		css_class: "single-column"
	};
};

frappe.wiz.on("before_load", function() {
	load_frappe_slides();

	// add welcome slide
	frappe.wiz.add_slide(frappe.wiz.welcome);
	frappe.wiz.add_slide(frappe.wiz.region);
	frappe.wiz.add_slide(frappe.wiz.user);
});
