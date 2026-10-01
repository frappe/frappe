frappe.provide("frappe.setup");
frappe.provide("frappe.setup.events");
frappe.provide("frappe.ui");

frappe.setup = {
	slides: [],
	events: {},
	data: {},
	utils: {},
	domains: [],
	// apps whose logos the intro shows; adjust it in a "before_load" handler
	intro_apps: [],

	on: function (event, fn) {
		if (!frappe.setup.events[event]) {
			frappe.setup.events[event] = [];
		}
		frappe.setup.events[event].push(fn);
	},
	add_slide: function (slide) {
		frappe.setup.slides.push(slide);
	},

	remove_slide: function (slide_name) {
		frappe.setup.slides = frappe.setup.slides.filter((slide) => slide.name !== slide_name);
	},

	run_event: function (event) {
		$.each(frappe.setup.events[event] || [], function (i, fn) {
			fn();
		});
	},
};

frappe.pages["setup-wizard"].on_page_load = function (wrapper) {
	if (frappe.boot.setup_complete) {
		window.location.href = frappe.boot.apps_data.default_path || "/desk";
	}
	let requires = frappe.boot.setup_wizard_requires || [];
	frappe.require(requires, function () {
		frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.load_languages",
			freeze: true,
			callback: function (r) {
				frappe.setup.data.lang = r.message;
				frappe.call({
					method: "frappe.desk.page.setup_wizard.setup_wizard.load_user_details",
					freeze: true,
					callback: function (r) {
						frappe.setup.data.full_name = r.message.full_name;
						frappe.setup.data.email = r.message.email;

						if (r.message.full_name) {
							frappe.setup.data.first_name = r.message.full_name.split(" ")[0];
						}

						// apps opt into the intro with `setup_wizard_text` on their add_to_apps_screen entry
						frappe.setup.intro_apps = (frappe.boot.apps_data?.apps || []).filter(
							(app) => app.logo && app.setup_wizard_text
						);
						frappe.setup.run_event("before_load");
						var wizard_settings = {
							parent: wrapper,
							slides: frappe.setup.slides,
							slide_class: frappe.setup.SetupWizardSlide,
							unidirectional: 1,
							done_state: 1,
						};
						frappe.wizard = new frappe.setup.SetupWizard(wizard_settings);
						frappe.setup.run_event("after_load");
						frappe.wizard.show_slide(cint(frappe.get_route()[1]));
					},
				});
			},
		});
	});
};

frappe.pages["setup-wizard"].on_page_show = function () {
	frappe.wizard && frappe.wizard.show_slide(cint(frappe.get_route()[1]));
};

frappe.setup.on("before_load", function () {
	if (
		frappe.boot.setup_wizard_completed_apps?.length &&
		frappe.boot.setup_wizard_completed_apps.includes("frappe")
	) {
		return;
	}

	// load slides
	frappe.setup.slides_settings.forEach((s) => {
		if (!(s.name === "user" && frappe.boot.developer_mode)) {
			// if not user slide with developer mode
			frappe.setup.add_slide(s);
		}
	});
});

frappe.setup.SetupWizard = class SetupWizard extends frappe.ui.Slides {
	constructor(args = {}) {
		super(args);
		$.extend(this, args);

		this.page_name = "setup-wizard";
		this.welcomed = true;
		frappe.set_route("setup-wizard/0");
	}

	make() {
		super.make();
		this.container.addClass("container setup-wizard-slide with-form");
		this.$next_btn.addClass("action");
		this.$complete_btn.addClass("action");
		this.setup_keyboard_nav();
		this.track_leaving();
		this.make_intro();
	}

	make_intro() {
		this.container.hide();
		this.step_shown_at = Date.now();

		const apps = frappe.setup.intro_apps;
		// one app speaks for itself; several share the generic line
		const tagline =
			apps.length === 1
				? apps[0].setup_wizard_text
				: __("Let's get your workspace ready. It only takes a few minutes.");

		this.$intro =
			$(`<div class="setup-intro flex flex-col items-center justify-center text-center">
			<div class="flex gap-3 mb-8 ${apps.length ? "" : "hidden"}">
				${apps.map((app) => `<img class="setup-intro__logo" src="${app.logo}" alt="">`).join("")}
			</div>
			<div class="setup-intro__hello grid text-12xl text-ink-gray-9" aria-hidden="true"></div>
			<p class="setup-intro__tagline mt-2 mb-0 text-p-lg text-ink-gray-5"></p>
		</div>`).appendTo(this.parent);
		this.$intro.find(".setup-intro__tagline").text(tagline);

		frappe.ui
			.button({
				label: __("Get Started"),
				icon_right: "arrow-right",
				variant: "solid",
				size: "lg",
				css_class: "setup-intro__start mt-6",
				onclick: () => this.close_intro(),
			})
			.appendTo(this.$intro);

		this.cycle_hello();
		this.capture("viewed_setup_intro", {
			apps: apps.map((app) => app.name),
			browser_language: navigator.language,
		});
	}

	cycle_hello() {
		const $hello = this.$intro.find(".setup-intro__hello");

		// start with the browser's language when we have a greeting for it
		const browser_langs = navigator.languages || [navigator.language];
		let index =
			browser_langs
				.map((code) => GREETINGS.findIndex(([lang]) => lang === code.split("-")[0]))
				.find((i) => i >= 0) ?? 0;

		const show = () => {
			$hello.find(".is-current").removeClass("is-current").addClass("is-leaving");
			const [code, greeting] = GREETINGS[index];
			$(`<span class="is-current"></span>`)
				.text(greeting)
				.attr("lang", code)
				.appendTo($hello);
			setTimeout(() => $hello.find(".is-leaving").remove(), 400);
			index = (index + 1) % GREETINGS.length;
			this.hello_timer = setTimeout(show, 3000);
		};

		// let the logos settle before the first word
		this.hello_timer = setTimeout(show, 400);
	}

	close_intro() {
		this.capture("started_setup", { duration_seconds: this.seconds_on_step() });
		this.step_shown_at = Date.now();
		clearTimeout(this.hello_timer);
		this.$intro.remove();
		this.$intro = null;
		this.container.show();
		this.container.find(".form-control:visible").first().focus();
	}

	setup_keyboard_nav() {
		this.on_enter_press = this.handle_enter_press.bind(this);
		$("body").on("keydown", this.on_enter_press);
	}

	disable_keyboard_nav() {
		$("body").off("keydown", this.on_enter_press);
	}

	handle_enter_press(e) {
		if (e.which === frappe.ui.keyCode.ENTER && this.$intro) {
			this.close_intro();
			e.preventDefault();
		} else if (e.which === frappe.ui.keyCode.ENTER) {
			let $target = $(e.target);
			if ($target.hasClass("prev-btn") || $target.hasClass("next-btn")) {
				$target.trigger("click");
			} else {
				// hitting enter on autocomplete field shouldn't trigger next slide.
				if ($target.data().fieldtype == "Autocomplete") return;

				this.container.find(".next-btn").trigger("click");
				e.preventDefault();
			}
		}
	}

	before_show_slide() {
		if (!this.welcomed) {
			frappe.set_route(this.page_name);
			return false;
		}
		return true;
	}

	show_slide(id) {
		if (id === this.slides.length) {
			return;
		}
		const from = this.current_id;
		super.show_slide(id);
		frappe.set_route(this.page_name, cstr(id));

		if (this.current_id === from) return;
		if (this.current_id === from + 1) {
			this.capture_step_completed(from);
		} else if (this.current_id < from && this.slides[from]) {
			this.capture("went_back_in_setup", {
				from_step: this.slides[from].name,
				to_step: this.slides[this.current_id].name,
			});
		}
		this.step_shown_at = Date.now();
	}

	// Setup events are sent even when the user opts out of telemetry on the first
	// slide: the opt-out applies once setup completes (see sync_telemetry_preference).
	capture(event, properties) {
		frappe.telemetry?.capture(event, "setup", properties);
	}

	capture_step_completed(index) {
		this.capture("completed_setup_step", {
			step: this.slides[index].name,
			step_number: index + 1,
			total_steps: this.slides.length,
			duration_seconds: this.seconds_on_step(),
		});
	}

	// time on the current slide, or on the intro while it is open
	seconds_on_step() {
		return this.step_shown_at ? Math.round((Date.now() - this.step_shown_at) / 1000) : null;
	}

	// Best effort: the event is lost if the page unloads before it is sent.
	track_leaving() {
		window.addEventListener("pagehide", () => {
			if (this.setup_submitted) return;
			this.capture("left_setup", {
				step: this.$intro ? "intro" : this.current_slide?.name,
				duration_seconds: this.seconds_on_step(),
			});
		});
	}

	sync_telemetry_preference() {
		// Apply the opt-out from the final committed values, not on each checkbox
		// change, so toggling within a slide stays reversible — disable() is one-way.
		// Server-side the preference lands only at wizard completion, so setup
		// events (funnel, persona) are captured regardless of the choice.
		if (frappe.telemetry.enabled && !this.values.enable_telemetry) {
			frappe.telemetry.disable();
		}
	}

	show_hide_prev_next(id) {
		super.show_hide_prev_next(id);
		if (id + 1 === this.slides.length) {
			this.$next_btn.hide();
			this.$complete_btn.show().on("click", () => this.action_on_complete());
		} else {
			this.$next_btn.show();
			this.$complete_btn.hide();
		}
	}

	refresh_slides() {
		// For Translations, etc.
		if (this.in_refresh_slides || !this.current_slide.set_values(true)) {
			return;
		}
		this.in_refresh_slides = true;

		this.update_values();
		const welcome_slide = frappe.setup.slides_settings.find((s) => s.name === "welcome");
		if (welcome_slide && this.values.language) {
			const lang_field = welcome_slide.fields.find((f) => f.fieldname === "language");
			if (lang_field) {
				lang_field.default = this.values.language;
			}
		}
		frappe.setup.slides = [];
		frappe.setup.run_event("before_load");

		frappe.setup.slides = this.get_setup_slides_filtered_by_domain();

		this.slides = frappe.setup.slides;
		frappe.setup.run_event("after_load");

		// re-render all slide, only remake made slides
		$.each(this.slide_dict, (id, slide) => {
			if (slide.made) {
				this.made_slide_ids.push(id);
			}
		});
		this.made_slide_ids.push(this.current_id);
		this.setup();

		this.show_slide(this.current_id);
		this.refresh(this.current_id);
		setTimeout(() => {
			this.container.find(".form-control").first().focus();
		}, 200);
		this.in_refresh_slides = false;
	}

	action_on_complete() {
		if (!this.current_slide.set_values()) return;
		this.setup_submitted = true;
		this.capture_step_completed(this.current_id);
		this.update_values();
		this.sync_telemetry_preference();
		this.show_working_state();
		this.disable_keyboard_nav();
		this.listen_for_setup_stages();

		return frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
			args: { args: this.values },
			callback: (r) => {
				if (r.message.status === "ok") {
					this.post_setup_success();
				} else if (r.message.status === "registered") {
					this.update_setup_message(__("Getting started"));
				} else if (r.message.fail !== undefined) {
					this.abort_setup(r.message.fail);
				}
			},
			error: () => this.abort_setup(),
		});
	}

	post_setup_success() {
		this.set_setup_load_percent(100);
		this.update_setup_message(__("All set! Opening your workspace"));
		if (frappe.setup.welcome_page) {
			localStorage.setItem("session_last_route", frappe.setup.welcome_page);
		}
		setTimeout(function () {
			// Reload
			let current_route = localStorage.current_route;

			localStorage.current_route = "";
			localStorage.current_app = "";

			window.location.href = current_route || frappe.boot.apps_data.default_path || "/desk";
		}, 2000);
	}

	abort_setup(fail_msg) {
		this.$working_state.find(".state-icon-container").addClass("hidden");
		fail_msg = fail_msg
			? fail_msg
			: frappe.last_response.setup_wizard_failure_message
			? frappe.last_response.setup_wizard_failure_message
			: __("We couldn't finish setting things up");

		this.$working_state.find(".title").html(__("Something went wrong"));
		this.$working_state.find(".setup-message").html(fail_msg);

		this.$abort_btn.show();
	}

	listen_for_setup_stages() {
		frappe.realtime.on("setup_task", (data) => {
			// console.log('data', data);
			if (data.stage_status) {
				this.update_setup_message(data.stage_status);
				// the stage is starting, not done: the bar fills only when setup succeeds
				this.set_setup_load_percent((data.progress[0] / data.progress[1]) * 100);
			}
			if (data.fail_msg) {
				this.abort_setup(data.fail_msg);
			}
			if (data.status === "ok") {
				this.post_setup_success();
			}
		});
	}

	update_setup_message(message) {
		this.get_setup_progress()?.set_label(message);
	}

	get_setup_slides_filtered_by_domain() {
		let filtered_slides = [];
		frappe.setup.slides.forEach(function (slide) {
			if (frappe.setup.domains) {
				let active_domains = frappe.setup.domains;
				if (
					!slide.domains ||
					slide.domains.filter((d) => active_domains.includes(d)).length > 0
				) {
					filtered_slides.push(slide);
				}
			} else {
				filtered_slides.push(slide);
			}
		});
		return filtered_slides;
	}

	show_working_state() {
		this.container.hide();
		frappe.set_route(this.page_name);

		this.$working_state = this.get_message(
			__("Setting things up"),
			__("This can take a minute. Please keep this page open.")
		).appendTo(this.parent);

		this.attach_abort_button();

		this.current_id = this.slides.length;
		this.current_slide = null;
	}

	attach_abort_button() {
		this.$abort_btn = frappe.ui.button({
			label: __("Try Again"),
			icon_left: "rotate-ccw",
			size: "md",
			css_class: "btn-abort mt-4",
		});
		this.$working_state.find(".content").append(this.$abort_btn);

		this.$abort_btn.on("click", () => {
			this.setup_submitted = false;
			$(this.parent).find(".setup-in-progress").remove();
			this.container.show();
			frappe.set_route(this.page_name, this.slides.length - 1);
		});

		this.$abort_btn.hide();
	}

	get_message(title, message = "") {
		return $(`<div class="slides-wrapper container setup-wizard-slide setup-in-progress w-full max-w-lg ms-auto me-auto">
			<div class="content">
				<h1 class="slide-title title m-0 text-3xl-semibold text-ink-gray-9">${title}</h1>
				<p class="setup-message mt-2 mb-0 text-p-sm text-ink-gray-5">${message}</p>
				<div class="state-icon-container mt-8"></div>
			</div>
		</div>`)
			.find(".state-icon-container")
			.append(frappe.ui.progress({ size: "md", label: __("Getting started") }))
			.end();
	}

	get_setup_progress() {
		return this.$working_state.find(".es-progress").data("es-progress");
	}

	set_setup_load_percent(percent) {
		this.get_setup_progress()?.set_value(percent);
	}
};

frappe.setup.SetupWizardSlide = class SetupWizardSlide extends frappe.ui.Slide {
	constructor(slide = null) {
		super(slide);
	}

	make() {
		super.make();
		this.set_init_values();
		this.reset_action_button_state();
	}

	set_init_values() {
		let me = this;
		// set values from frappe.setup.values
		if (frappe.wizard.values && this.fields) {
			this.fields.forEach(function (f) {
				var value = frappe.wizard.values[f.fieldname];
				if (value) {
					me.get_field(f.fieldname).set_input(value);
				}
			});
		}
	}
};

// Frappe slides settings
// ======================================================
frappe.setup.slides_settings = [
	{
		// Welcome (language) slide
		name: "welcome",
		title: () =>
			frappe.setup.data.first_name
				? __("Hi {0}, let's get the basics right", [frappe.setup.data.first_name])
				: __("Let's get the basics right"),
		help: __("These set how dates, numbers and money look across the app."),

		fields: [
			{
				fieldname: "language",
				label: __("Language"),
				fieldtype: "Autocomplete",
				placeholder: __("Select Language"),
				default: "English",
				reqd: 1,
			},
			{
				fieldname: "country",
				label: __("Country"),
				fieldtype: "Autocomplete",
				placeholder: __("Select Country"),
				reqd: 1,
			},
			{
				fieldname: "timezone",
				label: __("Time Zone"),
				placeholder: __("Select Time Zone"),
				fieldtype: "Select",
				reqd: 1,
			},
			{
				fieldname: "currency",
				label: __("Currency"),
				placeholder: __("Select Currency"),
				fieldtype: "Select",
				reqd: 1,
			},
			{
				fieldname: "enable_telemetry",
				label: __("Share usage data to help us improve"),
				fieldtype: "Check",
				default: cint(frappe.telemetry.can_enable()),
				depends_on: "eval:frappe.telemetry.can_enable()",
			},
		],

		onload: function (slide) {
			frappe.setup.utils.load_prefilled_data(slide, this.initialize_fields);
		},

		initialize_fields: function (slide) {
			const setup_fields = function (slide) {
				frappe.setup.utils.setup_region_fields(slide);
				frappe.setup.utils.setup_language_field(slide);
			};

			if (frappe.setup.data.regional_data) {
				setup_fields(slide);
			} else {
				frappe.setup.utils.load_regional_data(slide, setup_fields);
			}
			let current_selection = frappe.wizard.values.language;
			if (!slide.get_value("language")) {
				let session_language =
					current_selection ||
					frappe.setup.utils.get_language_name_from_code(
						frappe.setup.utils.get_browser_language() || frappe.boot.lang
					) ||
					"English";
				let language_field = slide.get_field("language");
				language_field.df.default = session_language;

				language_field.set_input(session_language);
				if (language_field.awesomplete) {
					language_field.awesomplete.evaluate();
				}
				if (!frappe.setup._from_load_messages) {
					language_field.$input.trigger("change");
				}
				delete frappe.setup._from_load_messages;
				moment.locale("en");
			}
			frappe.setup.utils.bind_region_events(slide);
			frappe.setup.utils.bind_language_events(slide);
		},
	},
	{
		// Profile slide
		name: "user",
		title: __("Create your account"),
		help: __("You'll use these details to sign in."),
		fields: [
			{
				fieldname: "full_name",
				label: __("Full Name"),
				fieldtype: "Data",
				reqd: 1,
			},
			{
				fieldname: "email",
				label: __("Email"),
				fieldtype: "Data",
				options: "Email",
			},
			{
				fieldname: "password",
				label:
					frappe.session.user === "Administrator"
						? __("Password")
						: __("Update Password"),
				fieldtype: "Password",
				length: 512,
				depends_on: "eval:!frappe.boot.is_fc_site",
			},
		],

		onload: function (slide) {
			slide.form.fields_dict.password?.$input?.attr("autocomplete", "new-password");

			if (frappe.session.user !== "Administrator") {
				const { first_name, last_name, email } = frappe.boot.user;
				if (first_name || last_name) {
					slide.form.fields_dict.full_name.set_input(
						[first_name, last_name].join(" ").trim()
					);
				}
				slide.form.fields_dict.email.set_input(email);
				slide.form.fields_dict.email.df.read_only = 1;
				slide.form.fields_dict.email.refresh();
			} else {
				if (!frappe.boot.is_fc_site) slide.form.fields_dict.password.df.reqd = 1;
				slide.form.fields_dict.password.refresh();
				if (frappe.setup.data.full_name) {
					slide.form.fields_dict.full_name.set_input(frappe.setup.data.full_name);
					slide.form.fields_dict.full_name.df.read_only = 1;
					slide.form.fields_dict.full_name.refresh();
				}
				if (frappe.setup.data.email) {
					slide.form.fields_dict.email.set_input(frappe.setup.data.email);
					slide.form.fields_dict.email.df.read_only = 1;
				}
				slide.form.fields_dict.email.df.reqd = 1;
				slide.form.fields_dict.email.refresh();
			}
		},
	},
];

frappe.setup.utils = {
	load_prefilled_data: function (slide, callback) {
		frappe.db
			.get_value("System Settings", "System Settings", [
				"country",
				"timezone",
				"currency",
				"language",
			])
			.then((r) => {
				if (r.message) {
					frappe.wizard.values.currency = r.message.currency;
					frappe.wizard.values.country = r.message.country;
					frappe.wizard.values.timezone = r.message.time_zone;
					frappe.wizard.values.language =
						frappe.wizard.values.language || r.message.language;

					frappe.db.get_value(
						"User",
						{ name: ["not in", ["Administrator", "Guest"]] },
						["full_name", "email"],
						(r) => {
							if (r) {
								frappe.wizard.values.full_name = r.full_name;
								frappe.wizard.values.email = r.email;
							}
						}
					);
				}
				callback(slide);
			});
	},

	load_regional_data: function (slide, callback) {
		frappe.call({
			method: "frappe.geo.country_info.get_country_timezone_info",
			callback: function (data) {
				frappe.setup.data.regional_data = data.message;
				callback(slide);
			},
		});
	},

	load_user_details: function (slide, callback) {
		frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.load_user_details",
			freeze: true,
			callback: function (r) {
				frappe.setup.data.full_name = r.message.full_name;
				frappe.setup.data.email = r.message.email;
				callback(slide);
			},
		});
	},

	setup_language_field: function (slide) {
		var language_field = slide.get_field("language");
		language_field.df.options = frappe.setup.data.lang.languages;
		if (frappe.wizard.values.language) {
			language_field.df.default = frappe.wizard.values.language;
		}
		language_field.set_options();
	},

	setup_region_fields: function (slide) {
		/*
			Set a slide's country, timezone and currency fields
		*/
		let data = frappe.setup.data.regional_data;
		let country_field = slide.get_field("country");
		let translated_countries = [];

		Object.keys(data.country_info)
			.sort()
			.forEach((country) => {
				translated_countries.push({
					label: __(country),
					value: country,
				});
			});

		country_field.set_data(translated_countries);

		slide
			.get_input("currency")
			.empty()
			.add_options(
				frappe.utils.unique($.map(data.country_info, (opts) => opts.currency).sort())
			);

		slide.get_input("timezone").empty().add_options(data.all_timezones);

		slide.get_field("currency").set_input(frappe.wizard.values.currency);
		slide.get_field("timezone").set_input(frappe.wizard.values.timezone);

		// set values if present
		let country =
			frappe.wizard.values.country ||
			data.default_country ||
			guess_country(frappe.setup.data.regional_data.country_info);

		if (country) {
			country_field.set_input(country);
			$(country_field.input).change();
		}
	},

	bind_language_events: function (slide) {
		slide
			.get_input("language")
			.unbind("change")
			.on("change", function () {
				const selected_language = $(this).val();
				if (slide.get_field("language").value === selected_language) return;

				clearTimeout(slide.language_call_timeout);
				slide.language_call_timeout = setTimeout(() => {
					let lang = selected_language || "English";
					frappe._messages = {};
					frappe.call({
						method: "frappe.desk.page.setup_wizard.setup_wizard.load_messages",
						freeze: true,
						args: {
							language: lang,
						},
						callback: function () {
							frappe.wizard.values.language = lang;
							frappe.setup._from_load_messages = true;
							frappe.wizard.refresh_slides();
						},
					});
				}, 500);
			});
	},

	get_language_name_from_code: function (language_code) {
		return frappe.setup.data.lang.codes_to_names[language_code] || "English";
	},

	// code of the first browser language this site has translations for
	get_browser_language: function () {
		const codes_to_names = frappe.setup.data.lang.codes_to_names;
		for (const code of navigator.languages || [navigator.language]) {
			const match = [code, code.split("-")[0]].find((c) => codes_to_names[c]);
			if (match) return match;
		}
	},

	bind_region_events: function (slide) {
		/*
			Bind a slide's country, timezone and currency fields
		*/
		slide.get_input("country").on("change", function () {
			let data = frappe.setup.data.regional_data;
			let country = slide.get_input("country").val();
			country = country.replace(/\s*\([^)]*\)/, "");
			if (!(country in data.country_info)) return;

			let $timezone = slide.get_input("timezone");

			$timezone.empty();

			if (!country) return;
			// add country specific timezones first
			const timezone_list = data.country_info[country].timezones || [];
			$timezone.add_options(timezone_list.sort());
			slide.get_field("currency").set_input(data.country_info[country].currency);
			slide.get_field("currency").$input.trigger("change");

			// add all timezones at the end, so that user has the option to change it to any timezone
			$timezone.add_options(data.all_timezones);
			slide.get_field("timezone").set_input($timezone.val());

			// temporarily set date format
			frappe.boot.sysdefaults.date_format =
				data.country_info[country].date_format || "dd-mm-yyyy";
		});

		slide.get_input("currency").on("change", function () {
			let currency = slide.get_input("currency").val();
			if (!currency) return;
			frappe.model.with_doc("Currency", currency, function () {
				frappe.provide("locals.:Currency." + currency);
				let currency_doc = frappe.model.get_doc("Currency", currency);
				let number_format = currency_doc.number_format;
				if (number_format === "#.###") {
					number_format = "#.###,##";
				} else if (number_format === "#,###") {
					number_format = "#,###.##";
				}

				frappe.boot.sysdefaults.number_format = number_format;
				locals[":Currency"][currency] = $.extend({}, currency_doc);
			});
		});
	},
};

// https://github.com/eggert/tz/blob/main/backward add more if required.
const TZ_BACKWARD_COMPATBILITY_MAP = {
	"Asia/Calcutta": "Asia/Kolkata",
};

function guess_country(country_info) {
	try {
		let system_timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
		system_timezone = TZ_BACKWARD_COMPATBILITY_MAP[system_timezone] || system_timezone;

		for (let [country, info] of Object.entries(country_info)) {
			let possible_timezones = (info.timezones || []).filter((t) => t == system_timezone);
			if (possible_timezones.length) return country;
		}
	} catch (e) {
		console.log("Could not guess country", e);
	}
}

// [language code, "Hello"] for the setup intro. Not translated on
// purpose: each greeting is in its own language. Main world languages, weighted
// towards where our users are.
const GREETINGS = [
	["en", "Hello"],
	["ar", "مرحبا"],
	["hi", "नमस्ते"],
	["zh", "你好"],
	["sw", "Habari"],
	["de", "Hallo"],
	["fr", "Bonjour"],
	["es", "Hola"],
	["pt", "Olá"],
	["bn", "নমস্কার"],
	["ja", "こんにちは"],
	["ru", "Привет"],
	["ur", "السلام علیکم"],
	["id", "Halo"],
	["tr", "Merhaba"],
	["fa", "سلام"],
	["ta", "வணக்கம்"],
	["ko", "안녕하세요"],
	["ki", "Wĩ mwega"],
];
