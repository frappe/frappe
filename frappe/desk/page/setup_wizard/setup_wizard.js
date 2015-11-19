frappe.provide("frappe.wiz");
frappe.provide("frappe.wiz.events");

frappe.wiz = {
	slides: [],
	events: {},
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
			fn(frappe.wiz.wizard);
		});
	}
}

frappe.pages['setup-wizard'].on_page_load = function(wrapper) {
	// setup page ui
	$(".navbar:first").toggle(false);
	$("body").css({"padding-top":"30px"});

	frappe.require("/assets/frappe/css/animate.min.css");

	$.each(frappe.boot.setup_wizard_requires || [], function(i, path) {
		frappe.require(path);
	});

	frappe.wiz.run_event("before_load");

	var wizard_settings = {
		page_name: "setup-wizard",
		parent: wrapper,
		slides: frappe.wiz.slides,
		title: __("Welcome")
	}

	frappe.wiz.wizard = new frappe.wiz.Wizard(wizard_settings);

	frappe.wiz.run_event("after_load");
}

frappe.pages['setup-wizard'].on_page_show = function(wrapper) {
	if(frappe.get_route()[1]) {
		frappe.wiz.wizard.show(frappe.get_route()[1]);
	}
}

frappe.wiz.Wizard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.slides;
		this.slide_dict = {};
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
		if(this.current_slide && this.current_slide.id===id)
			return;
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
			$.extend(values, slide.values)
		})
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
		var values = me.get_values();
		me.show_working();
		return frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
			args: {args: values},
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

		if(this.id > 0) {
			this.$prev = this.$body.find('.prev-btn').removeClass("hide")
				.click(function() {
					frappe.set_route(me.wiz.page_name, me.id-1 + "");
				})
				.css({"margin-right": "10px"});
			}
		if(this.id+1 < this.wiz.slides.length) {
			this.$next = this.$body.find('.next-btn').removeClass("hide")
				.click(function() {
					me.values = me.form.get_values();
					if(me.values===null)
						return;
					if(me.validate && !me.validate())
						return;
					frappe.set_route(me.wiz.page_name, me.id+1 + "");
				})
		} else {
			this.$complete = this.$body.find('.complete-btn').removeClass("hide")
				.click(function() {
					me.values = me.form.get_values();
					if(me.values===null)
						return;
					if(me.validate && !me.validate())
						return;
					me.wiz.on_complete(me.wiz);
				})
		}

		if(this.onload) {
			this.onload(this);
		}

	},
	get_input: function(fn) {
		return this.form.get_input(fn);
	},
	get_field: function(fn) {
		return this.form.get_field(fn);
	}
});

function load_frappe_slides() {
	// language selection
	frappe.wiz.welcome = {
		name: "welcome",
		title: __("Welcome"),
		icon: "icon-world",
		help: __("Let's prepare the system for first use."),

		fields: [
			{ fieldname: "language", label: __("Select Your Language"), reqd:1,
				fieldtype: "Select" },
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
				callback: function(r) {
					frappe.wiz.welcome.data = r.message;
					frappe.wiz.welcome.setup_fields(slide);

					slide.get_field("language")
						.set_input(frappe.wiz.welcome.data.default_language || "english");
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
					args: {
						language: lang
					},
					callback: function(r) {
						// TODO save values!

						// reset all slides so that labels are translated
						frappe.wiz.slides = [];
						frappe.wiz.run_event("before_load");
						frappe.wiz.wizard.slides = frappe.wiz.slides;
						frappe.wiz.run_event("after_load");

						// re-render all slides
						$.each(slide.wiz.slide_dict, function(id, s) {
							$.extend(s, frappe.wiz.slides[id]);
							s.make();
						});

						// select is re-made after language change
						var select = slide.get_field("language");
						select.set_input(lang);
					}
				});
			});
		}
	}

	// region selection
	frappe.wiz.region = {
		title: __("Region"),
		icon: "icon-flag",
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
			frappe.call({
				method:"frappe.geo.country_info.get_country_timezone_info",
				callback: function(data) {
					frappe.wiz.region.data = data.message;
					frappe.wiz.region.setup_fields(slide);
					frappe.wiz.region.bind_events(slide);
				}
			});
		},
		css_class: "single-column",
		setup_fields: function(slide) {
			var data = frappe.wiz.region.data;

			slide.get_input("country").empty()
				.add_options([""].concat(keys(data.country_info).sort()));

			slide.get_input("currency").empty()
				.add_options(frappe.utils.unique([""].concat($.map(data.country_info,
					function(opts, country) { return opts.currency; }))).sort());

			slide.get_input("timezone").empty()
				.add_options([""].concat(data.all_timezones));

			if (data.default_country) {
				slide.set_input("country", data.default_country);
			}
		},

		bind_events: function(slide) {
			slide.get_input("country").on("change", function() {
				var country = slide.get_input("country").val();
				var $timezone = slide.get_input("timezone");
				var data = frappe.wiz.region.data;

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
	};
};

frappe.wiz.on("before_load", function() {
	load_frappe_slides();

	// add welcome slide
	frappe.wiz.add_slide(frappe.wiz.welcome);
	frappe.wiz.add_slide(frappe.wiz.region);
});
