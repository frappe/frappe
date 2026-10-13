import Widget from "./base_widget.js";

frappe.provide("frappe.utils");

export default class OnboardingWidget extends Widget {
	async refresh() {
		this.new && (await this.get_onboarding_data());
		this.set_title();
		this.set_actions();
		this.set_body();
		this.setup_events();
	}

	get_config() {
		return {
			label: this.onboarding_name,
		};
	}

	make_body() {
		this.body.empty();
		this.$done = null;
		this.progress = new frappe.ui.Progress({
			intervals: true,
			interval_count: this.get_required_steps().length,
			size: "md",
		});
		this.steps_wrapper = $(`<div class="flex flex-col gap-0.5"></div>`);
		this.body.append(this.progress.$el, this.steps_wrapper);

		// each step is built once and updated in place, so opening one can animate
		this.step_elements = new Map();
		this.steps.forEach((step) => {
			const $step = this.make_step(step);
			this.step_elements.set(step, $step);
			this.steps_wrapper.append($step);
		});

		this.update_progress();
		this.set_open_step(this.get_next_step());
	}

	// An onboarding whose steps lead to other onboardings is where a new user starts, so it greets
	// them and keeps its own title for the line below.
	leads_to_onboardings() {
		return this.steps?.some((step) => step.action === "Complete Onboarding");
	}

	set_title() {
		if (!this.leads_to_onboardings()) return super.set_title();

		const hour = new Date().getHours();
		// Administrator's first name is the account's name, not a person's
		const name = frappe.session.user === "Administrator" ? "" : frappe.boot.user.first_name;
		let greeting;
		// the small hours are still the evening before
		if (hour >= 5 && hour < 12) {
			greeting = name ? __("Good morning, {0}", [name]) : __("Good morning");
		} else if (hour >= 12 && hour < 17) {
			greeting = name ? __("Good afternoon, {0}", [name]) : __("Good afternoon");
		} else {
			greeting = name ? __("Good evening, {0}", [name]) : __("Good evening");
		}
		this.title_field.empty().append($(`<span class="ellipsis"></span>`).text(greeting));
	}

	// Optional steps show what else the module can do; progress and completion count the rest.
	get_required_steps() {
		const required = this.steps.filter((step) => !step.is_optional);
		return required.length ? required : this.steps;
	}

	update_progress() {
		const required = this.get_required_steps();
		const total = required.length;
		const completed = required.filter((step) => step.is_complete).length;
		const skipped = required.filter((step) => !step.is_complete && step.is_skipped).length;

		// a skipped step needs no more doing, so it fills the bar, but it isn't counted as done
		this.progress.set_value(((completed + skipped) / total) * 100);
		const progress = skipped
			? __("{0} of {1} done · {2} skipped", [completed, total, skipped])
			: __("{0} of {1} steps done", [completed, total]);
		this.subtitle_field.text(
			this.leads_to_onboardings() ? `${this.title} · ${progress}` : progress
		);
		if (completed + skipped === total) this.show_success();
	}

	make_step(step) {
		const $step = $(`<div class="onboarding-step rounded-md px-2">
			<button type="button" class="onboarding-step-head flex items-center gap-2 w-full">
				<span class="step-icon shrink-0 flex"></span>
				<span class="step-module hidden shrink-0"></span>
				<span class="step-title text-base truncate"></span>
				${step.is_optional ? frappe.ui.badge.html({ label: __("Optional"), size: "sm" }) : ""}
				<span class="step-skipped hidden text-p-sm text-ink-gray-4 ms-auto">${__("Skipped")}</span>
			</button>
			<div class="onboarding-step-collapse">
				<div class="onboarding-step-body"></div>
			</div>
			<div class="onboarding-step-media"></div>
		</div>`);
		$step.find(".step-title").text(step.title);
		// a step leading to a module's onboarding is named by the module, which people choose by
		if (step.module) {
			const shell = frappe.boot.module_sidebars?.[get_shell(step.module)];
			$step
				.find(".step-module")
				.text(__(shell?.label || step.module))
				.removeClass("hidden");
		}
		// the whole row takes the click, not only the title button inside its padding; the button
		// keeps it reachable from the keyboard, and its click bubbles up to here
		$step.on("click", () => step !== this.open_step && this.set_open_step(step));
		return $step;
	}

	set_open_step(step) {
		if (step && step !== this.open_step) {
			// filled on opening, so a closed step loads no thumbnail and shows its current state
			const $step = this.step_elements.get(step);
			$step.find(".onboarding-step-body").empty().append(this.make_step_content(step));

			const video_id = get_youtube_id(step.intro_video_url);
			$step.toggleClass("has-media", !!video_id);
			$step
				.find(".onboarding-step-media")
				.empty()
				.append(video_id ? this.make_video(step, video_id) : null);
		}
		this.open_step = step;
		this.steps.forEach((s) => this.update_step(s));
	}

	update_step(step) {
		const is_open = step === this.open_step;
		const is_done = step.is_complete || step.is_skipped;
		const $step = this.step_elements.get(step);

		$step.toggleClass("is-open", is_open);
		$step.find(".onboarding-step-head").attr("aria-expanded", is_open);
		$step.find(".step-icon").html(this.get_step_icon(step, is_open));
		// beside a module's name, the step's own title is the quieter half, open or not
		const has_module = !!step.module;
		const $label = has_module ? $step.find(".step-module") : $step.find(".step-title");
		$label
			.toggleClass("text-base-medium text-ink-gray-9", is_open)
			.toggleClass("text-base", !is_open)
			.toggleClass("text-ink-gray-5", !is_open && !!step.is_complete)
			.toggleClass("text-ink-gray-4", !is_open && !step.is_complete && !!step.is_skipped)
			.toggleClass("text-ink-gray-8", !is_open && !is_done);
		if (has_module) {
			$step
				.find(".step-title")
				.toggleClass("text-ink-gray-5", !step.is_skipped || !!step.is_complete)
				.toggleClass("text-ink-gray-4", !step.is_complete && !!step.is_skipped);
		}
		$step.find(".step-skipped").toggleClass("hidden", !step.is_skipped);
	}

	get_step_icon(step, is_open) {
		if (step.is_complete) {
			return frappe.utils.icon(
				"circle-check",
				"sm",
				"",
				"--icon-stroke: var(--ink-green-7)"
			);
		}
		if (step.is_skipped) {
			return frappe.utils.icon(
				"circle-dashed",
				"sm",
				"",
				"--icon-stroke: var(--ink-gray-4)"
			);
		}
		const module_icon = frappe.get_module_icon(get_shell(step.module));
		if (module_icon) return frappe.utils.icon(module_icon, "sm");

		const stroke = is_open ? "--ink-gray-8" : "--ink-gray-4";
		return frappe.utils.icon("circle", "sm", "", `--icon-stroke: var(${stroke})`);
	}

	make_step_content(step) {
		const $body = $(`<div class="onboarding-step-content flex flex-col gap-3"></div>`);

		if (step.description) {
			$(`<div class="onboarding-step-description text-p-sm text-ink-gray-6"></div>`)
				.html(frappe.markdown(step.description))
				.on("click", "a", (e) =>
					this.capture_step_event("step_docs_opened", step, {
						url: e.currentTarget.href,
					})
				)
				.appendTo($body);
		}

		const $actions = $(`<div class="flex items-center gap-2"></div>`).appendTo($body);
		$actions.append(
			frappe.ui.button({
				label: step.action_label || step.title,
				variant: "solid",
				icon_right: "arrow-right",
				onclick: () => this.run_action(step),
			})
		);
		if (step.can_import) {
			$actions.append(
				frappe.ui.button({
					label: __("Import"),
					variant: "subtle",
					icon: "import",
					onclick: () => this.import_records(step),
				})
			);
		}
		if (!step.is_complete && !step.is_skipped) {
			$actions.append(
				frappe.ui.button({
					label: __("Skip"),
					variant: "subtle",
					onclick: () => this.skip_step(step),
				})
			);
		}
		return $body;
	}

	// Only the thumbnail loads with the page; the player, and YouTube's cookies with it, wait
	// for a click.
	make_video(step, video_id) {
		const $video = $(`<button type="button" class="onboarding-video">
			<img alt="" decoding="async">
			<span class="onboarding-video-play">${frappe.utils.icon("play", "md")}</span>
		</button>`).attr("aria-label", __("Play video"));

		// maxresdefault only exists for HD uploads; a missing one comes back as an error or as
		// YouTube's 120px grey placeholder, and hqdefault always exists
		const img = $video.find("img")[0];
		const fall_back = () => (img.src = `https://i.ytimg.com/vi/${video_id}/hqdefault.jpg`);
		img.onerror = fall_back;
		img.onload = () =>
			img.src.includes("maxresdefault") && img.naturalWidth <= 120 && fall_back();
		img.src = `https://i.ytimg.com/vi/${video_id}/maxresdefault.jpg`;

		$video.on("click", () => {
			this.capture_step_event("step_video_played", step);
			$video.replaceWith(
				$(`<iframe class="onboarding-video-player"
					allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
					referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>`).attr({
					src: `https://www.youtube-nocookie.com/embed/${video_id}?autoplay=1`,
					title: __("YouTube video player"),
				})
			);
		});
		return $video;
	}

	run_action(step) {
		if (step.route_options && step.action !== "View Docs") {
			frappe.route_options = JSON.parse(step.route_options);
		}

		const actions = {
			"Create Entry": (step) => {
				if (step.is_complete) {
					frappe.set_route("List", step.reference_document);
				} else if (step.show_full_form || step.is_submittable) {
					// a draft from the quick entry would not finish a step that needs a submit
					this.create_entry(step);
				} else {
					this.show_quick_entry(step);
				}
			},
			"Show Form Tour": (step) => this.show_form_tour(step),
			"Update Settings": (step) => this.update_settings(step),
			"View Report": (step) => this.open_report(step),
			"Go to Page": (step) => this.go_to_page(step),
			"View Docs": (step) => this.view_docs(step),
			// the step is done when that module's own onboarding is, so opening it ticks nothing
			"Complete Onboarding": (step) =>
				frappe.app.sidebar.open_module(get_shell(step.module)),
		};
		actions[step.action]?.(step);
	}

	view_docs(step) {
		this.capture_step_event("step_docs_opened", step, { url: step.path });
		window.open(step.path, "_blank", "noopener");
		this.mark_complete(step);
	}

	// Opening the page is the step.
	go_to_page(step) {
		this.mark_complete(step).then(() => {
			// a path outside the desk, like another app's `/banking`, is a page load, not a route
			if (step.path.startsWith("/") && !step.path.startsWith("/desk")) {
				window.location.href = step.path;
			} else {
				frappe.set_route(step.path);
			}
		});
	}

	open_report(step) {
		const route = frappe.utils.generate_route({
			name: step.reference_report,
			type: "report",
			is_query_report: step.report_type !== "Report Builder",
			doctype: step.report_reference_doctype,
		});
		this.mark_complete(step, step.report_description).then(() => frappe.set_route(route));
	}

	show_form_tour(step) {
		const route = step.is_single
			? frappe.router.slug(step.reference_document)
			: `${frappe.router.slug(step.reference_document)}/new`;
		const return_to = frappe.get_route();

		this.set_route_hooks(step, {
			after_load: (frm) => {
				const on_finish = () => this.complete_and_return(step, return_to);
				frm.tour
					.init({ tour_name: step.form_tour, on_finish })
					.then(() => frm.tour.start());
			},
		});
		frappe.set_route(route);
	}

	update_settings(step) {
		const return_to = frappe.get_route();

		this.set_route_hooks(step, {
			after_load: (frm) => {
				frm.scroll_to_field(step.field);
				frm.doc.__unsaved = true;
			},
			// the server checks the saved value; if it is not the expected one the user stays on
			// the form with the reason
			after_save: () => this.complete_and_return(step, return_to),
		});
		frappe.set_route("Form", step.reference_document);
	}

	// frappe.route_hooks is one global that the next form to load, save or submit takes, whatever
	// its doctype. A hook for this step's form that reaches another form puts itself back and does
	// nothing there, so leaving the step half done and submitting, say, a Sales Invoice neither
	// ticks the step on the wrong form nor uses the hook up before the step's own form comes back.
	set_route_hooks(step, hooks) {
		frappe.route_hooks = {};
		for (const [event, callback] of Object.entries(hooks)) {
			const hook = (frm) => {
				if (frm?.doctype !== step.reference_document) {
					frappe.route_hooks[event] = hook;
					return;
				}
				callback(frm);
			};
			frappe.route_hooks[event] = hook;
		}
	}

	async create_entry(step) {
		const return_to = frappe.get_route();
		const docname = await this.get_first_document(step.reference_document);

		const hooks = {};
		if (step.form_tour) {
			hooks.after_load = (frm) => {
				frm.tour.init({ tour_name: step.form_tour }).then(() => frm.tour.start());
			};
		}

		if (step.is_submittable) {
			hooks.after_save = () => {
				frappe.ui.toast({ message: __("Submit it to finish this step."), type: "info" });
			};
			hooks.after_submit = () => this.complete_and_return(step, return_to);
		} else {
			hooks.after_save = () => this.complete_and_return(step, return_to);
		}
		this.set_route_hooks(step, hooks);

		frappe.set_route("Form", step.reference_document, docname);
	}

	show_quick_entry(step) {
		frappe.ui.form.make_quick_entry(
			step.reference_document,
			() => this.mark_complete(step),
			null,
			null,
			true
		);
	}

	// The import dialog the empty list view offers, opened here so the user stays in the onboarding.
	import_records(step) {
		frappe.require("data_import_tools.bundle.js", () => {
			frappe.data_import.open_data_import_dialog({
				reference_doctype: step.reference_document,
				import_type: "Insert New Records",
				on_close: () => this.refresh_step(step),
			});
		});
	}

	// Ask the server whether the step's work is done now, and tick it off if so. Closing an import
	// that brought nothing in leaves the step as it was, without an error.
	refresh_step(step) {
		if (step.is_complete) return;
		frappe
			.xcall("frappe.desk.doctype.onboarding_step.onboarding_step.get_onboarding_steps", {
				ob_steps: [{ step: step.name }],
			})
			.then(([fresh]) => fresh?.is_complete && this.mark_complete(step));
	}

	// Tick the step off, then go back to the onboarding. If the server says the work isn't done,
	// the error shows and the user stays where they are to finish it.
	complete_and_return(step, return_to) {
		return this.mark_complete(step).then(() => frappe.set_route(return_to));
	}

	mark_complete(step, description) {
		return this.update_step_status(step, "is_complete").then(() => {
			frappe.ui.toast({
				message: __("Done: {0}", [step.title]),
				description: description && description !== step.title ? description : "",
				type: "success",
			});
		});
	}

	skip_step(step) {
		return this.update_step_status(step, "is_skipped");
	}

	update_step_status(step, field) {
		// a step done means the hooks set up for it are spent
		frappe.route_hooks = {};

		return frappe
			.xcall("frappe.desk.desktop.update_onboarding_step", {
				name: step.name,
				field: field,
				value: 1,
			})
			.then(() => {
				step[field] = 1;
				this.update_progress();
				this.set_open_step(this.get_next_step(step));
			});
	}

	get_next_step(after) {
		const start = after ? this.steps.indexOf(after) + 1 : 0;
		const ordered = [...this.steps.slice(start), ...this.steps.slice(0, start)];
		return ordered.find((step) => !step.is_complete && !step.is_skipped);
	}

	show_success() {
		if (this.$done) return;
		const $done = (this.$done =
			$(`<div class="flex items-center justify-between gap-3 px-2 py-2">
			<span class="text-p-sm text-ink-gray-6">${__("You're all set.")}</span>
		</div>`));
		$done.append(
			frappe.ui.button({
				label: __("Done"),
				variant: "solid",
				onclick: () => this.hide(),
			})
		);
		this.body.append($done);
	}

	hide() {
		this.delete(true, true);
		this.widget.closest(".ce-block").hide();
	}

	set_body() {
		this.widget.addClass("onboarding-widget-box");
		this.body.addClass("flex flex-col gap-4");
		if (this.is_dismissed()) {
			this.widget.hide();
		} else {
			this.make_body();
		}
	}

	is_dismissed() {
		if (this.in_customize_mode) return false;

		let dismissed = JSON.parse(localStorage.getItem("dismissed-onboarding") || "{}");
		if (Object.keys(dismissed).includes(this.title)) {
			let last_hidden = new Date(dismissed[this.title]);
			let today = new Date();
			let diff = frappe.datetime.get_hour_diff(today, last_hidden);
			return diff < 24;
		}
		return false;
	}

	set_actions() {
		if (this.in_customize_mode) return;

		this.action_area.empty().append(
			frappe.ui.button({
				label: __("Dismiss", null, "Stop showing the onboarding widget."),
				variant: "ghost",
				onclick: () => {
					let dismissed = JSON.parse(
						localStorage.getItem("dismissed-onboarding") || "{}"
					);
					dismissed[this.title] = frappe.datetime.now_datetime();
					localStorage.setItem("dismissed-onboarding", JSON.stringify(dismissed));

					this.hide();
					frappe.telemetry.capture("onboarding_dismissed", "frappe_onboarding", {
						onboarding: this.label,
					});
				},
			})
		);
	}

	// What people open from a step, so the funnel shows whether its videos and docs get used
	capture_step_event(event, step, properties = {}) {
		frappe.telemetry.capture(event, "frappe_onboarding", {
			step: step.name,
			onboarding: this.label,
			...properties,
		});
	}

	get_onboarding_data() {
		return frappe.model
			.with_doc("Module Onboarding", this.onboarding_name)
			.then((onboarding_doc) => {
				if (onboarding_doc) {
					this.onboarding_doc = onboarding_doc;
					this.title = onboarding_doc.title || __("Let's Get Started");
					const method =
						"frappe.desk.doctype.onboarding_step.onboarding_step.get_onboarding_steps";
					return frappe
						.xcall(method, { ob_steps: onboarding_doc.steps })
						.then((steps) => {
							this.steps = steps;
						});
				}
			});
	}

	async get_first_document(doctype) {
		const { message } = await frappe.db.get_value(
			"Form Tour",
			{ reference_doctype: doctype },
			["first_document"]
		);
		let docname;

		if (message.first_document) {
			await frappe.db.get_list(doctype, { order_by: "creation" }).then((res) => {
				if (Array.isArray(res) && res.length) docname = res[0].name;
			});
		}

		return docname || "new";
	}
}

// A shell is keyed by its sidebar's name, which is not always its module's: the Quality sidebar
// is the Quality Management module's.
function get_shell(module) {
	const shells = frappe.boot.module_sidebars || {};
	if (!module || shells[module]) return module;
	return Object.keys(shells).find((name) => shells[name].module === module);
}

/**
 * The video id in a YouTube link: watch?v=, youtu.be/, shorts/, live/, embed/ and v/, on
 * youtube.com or youtube-nocookie.com. A bare id is accepted as is, since that is what the field
 * used to hold.
 */
function get_youtube_id(value) {
	value = (value || "").trim();
	if (/^[\w-]{11}$/.test(value)) return value;

	let url;
	try {
		url = new URL(value);
	} catch {
		return null;
	}

	const host = url.hostname.replace(/^(www|m|music)\./, "");
	let id = null;
	if (host === "youtu.be") {
		id = url.pathname.split("/")[1];
	} else if (host === "youtube.com" || host === "youtube-nocookie.com") {
		id =
			url.pathname === "/watch"
				? url.searchParams.get("v")
				: url.pathname.match(/^\/(?:embed|shorts|live|v)\/([\w-]+)/)?.[1];
	}
	return id && /^[\w-]{6,}$/.test(id) ? id : null;
}
