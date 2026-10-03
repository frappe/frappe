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
			interval_count: this.steps.length,
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

	update_progress() {
		const total = this.steps.length;
		const completed = this.steps.filter((step) => step.is_complete).length;
		const skipped = this.steps.filter((step) => !step.is_complete && step.is_skipped).length;

		// a skipped step needs no more doing, so it fills the bar, but it isn't counted as done
		this.progress.set_value(((completed + skipped) / total) * 100);
		this.subtitle_field.text(
			skipped
				? __("{0} of {1} done · {2} skipped", [completed, total, skipped])
				: __("{0} of {1} steps done", [completed, total])
		);
		if (completed + skipped === total) this.show_success();
	}

	make_step(step) {
		const $step = $(`<div class="onboarding-step rounded-md px-2">
			<button type="button" class="onboarding-step-head flex items-center gap-2 w-full">
				<span class="step-icon shrink-0 flex"></span>
				<span class="step-title truncate"></span>
				<span class="step-skipped hidden text-p-sm text-ink-gray-4 ms-auto">${__("Skipped")}</span>
			</button>
			<div class="onboarding-step-collapse">
				<div class="onboarding-step-body"></div>
			</div>
			<div class="onboarding-step-media"></div>
		</div>`);
		$step.find(".step-title").text(step.title);
		$step.find(".onboarding-step-head").on("click", () => this.set_open_step(step));
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
				.append(video_id ? this.make_video(video_id) : null);
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
		$step
			.find(".step-title")
			.toggleClass("text-base-medium text-ink-gray-9", is_open)
			.toggleClass("text-base", !is_open)
			.toggleClass("text-ink-gray-5", !is_open && !!step.is_complete)
			.toggleClass("text-ink-gray-4", !is_open && !step.is_complete && !!step.is_skipped)
			.toggleClass("text-ink-gray-8", !is_open && !is_done);
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
		const stroke = is_open ? "--ink-gray-8" : "--ink-gray-4";
		return frappe.utils.icon("circle", "sm", "", `--icon-stroke: var(${stroke})`);
	}

	make_step_content(step) {
		const $body = $(`<div class="onboarding-step-content flex flex-col gap-3"></div>`);

		if (step.description) {
			$(`<div class="onboarding-step-description text-p-sm text-ink-gray-6"></div>`)
				.html(frappe.markdown(step.description))
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
	make_video(video_id) {
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
		const actions = {
			"Create Entry": (step) => {
				if (step.is_complete) {
					frappe.set_route(`/desk/List/${step.reference_document}`);
				} else if (step.show_full_form) {
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
		};
		actions[step.action]?.(step);
	}

	view_docs(step) {
		window.open(step.path, "_blank", "noopener");
		this.mark_complete(step);
	}

	go_to_page(step) {
		this.mark_complete(step);
		frappe.set_route(step.path).then(() => {
			let message =
				step.callback_message ||
				__("You can continue with the onboarding after exploring this page");
			let title = step.callback_title || __("Awesome Work");

			let msg_dialog = frappe.msgprint({
				message: message,
				title: title,
				primary_action: {
					action: () => {
						msg_dialog.hide();
					},
					label: () => __("Continue"),
				},
				wide: true,
			});
		});
	}

	open_report(step) {
		let route = frappe.utils.generate_route({
			name: step.reference_report,
			type: "report",
			is_query_report: step.report_type !== "Report Builder",
			doctype: step.report_reference_doctype,
		});

		let current_route = frappe.get_route();

		frappe.set_route(route).then(() => {
			let msg_dialog = frappe.msgprint({
				message: __(step.report_description),
				title: __(step.reference_report),
				primary_action: {
					action: () => {
						frappe.set_route(current_route).then(() => {
							this.mark_complete(step);
						});
						msg_dialog.hide();
					},
					label: () => __("Continue"),
				},
				secondary_action: {
					action: () => {
						msg_dialog.hide();
						frappe.set_route(current_route).then(() => {
							this.mark_complete(step);
						});
					},
					label: __("Go Back"),
				},
			});

			frappe.msg_dialog.custom_onhide = () => this.mark_complete(step);
		});
	}

	show_form_tour(step) {
		let route;
		if (step.is_single) {
			route = frappe.router.slug(step.reference_document);
		} else {
			route = `${frappe.router.slug(step.reference_document)}/new`;
		}

		let current_route = frappe.get_route();

		frappe.route_hooks = {};
		frappe.route_hooks.after_load = (frm) => {
			const on_finish = () => {
				let msg_dialog = frappe.msgprint({
					message: __("Let's take you back to onboarding"),
					title: __("Onboarding complete"),
					primary_action: {
						action: () => {
							frappe.set_route(current_route).then(() => {
								this.mark_complete(step);
							});
							msg_dialog.hide();
						},
						label: () => __("Continue"),
					},
				});
			};
			const tour_name = step.form_tour;
			frm.tour.init({ tour_name, on_finish }).then(() => frm.tour.start());
		};

		frappe.set_route(route);
	}

	update_settings(step) {
		let current_route = frappe.get_route();

		frappe.route_hooks = {};
		frappe.route_hooks.after_load = (frm) => {
			frm.scroll_to_field(step.field);
			frm.doc.__unsaved = true;
		};

		frappe.route_hooks.after_save = (frm) => {
			let success = false;
			let args = {};

			let value = frm.doc[step.field];
			let custom_onhide = null;

			if (value && step.value_to_validate == "%") success = true;
			if (value == step.value_to_validate) success = true;
			if (cstr(value) == cstr(step.value_to_validate)) success = true;

			if (success) {
				args.message = __("Let's take you back to onboarding");
				args.title = __("Action Complete");
				args.primary_action = {
					action: () => {
						frappe.set_route(current_route).then(() => {
							this.mark_complete(step);
						});
					},
					label: __("Continue"),
				};

				custom_onhide = () => args.primary_action.action();
			} else {
				args.message = __("Looks like you didn't change the value");
				args.title = __("Try Again");
				args.secondary_action = {
					action: () => frappe.set_route(current_route),
					label: __("Go Back"),
				};

				args.primary_action = {
					action: () => {
						frappe.set_route(current_route).then(() => {
							setTimeout(() => {
								this.skip_step(step);
							}, 300);
						});
					},
					label: __("Skip Step"),
				};

				custom_onhide = () => args.secondary_action.action();
			}

			frappe.msgprint(args);
			frappe.msg_dialog.custom_onhide = () => custom_onhide();
		};

		frappe.set_route("Form", step.reference_document);
	}

	async create_entry(step) {
		let current_route = frappe.get_route();
		let docname = await this.get_first_document(step.reference_document);

		frappe.route_hooks = {};
		frappe.route_hooks.after_load = (frm) => {
			const on_finish = () => {
				frappe.msgprint({
					message: __("Awesome, now try making an entry yourself"),
					title: __("Document Saved"),
					primary_action: {
						action: () => {
							frappe.set_route(current_route).then(() => {
								this.mark_complete(step);
							});
						},
						label: __("Continue"),
					},
				});

				frappe.msg_dialog.custom_onhide = () => {
					this.mark_complete(step);
				};
			};
			const tour_name = step.form_tour;
			frm.tour.init({ tour_name, on_finish }).then(() => frm.tour.start());
		};

		let callback = () => {
			frappe.msgprint({
				message: __("Let's take you back to onboarding"),
				title: __("Action Complete"),
				primary_action: {
					action: () => {
						frappe.set_route(current_route).then(() => {
							this.mark_complete(step);
						});
					},
					label: __("Continue"),
				},
			});

			frappe.msg_dialog.custom_onhide = () => {
				this.mark_complete(step);
			};
		};

		if (step.is_submittable) {
			frappe.route_hooks.after_save = () => {
				frappe.msgprint({
					message: __("Submit this document to complete this step."),
					title: __("Document Saved"),
				});
			};
			frappe.route_hooks.after_submit = callback;
		} else {
			frappe.route_hooks.after_save = callback;
		}

		frappe.set_route("Form", step.reference_document, docname);
	}

	show_quick_entry(step) {
		let current_route = frappe.get_route_str();
		frappe.ui.form.make_quick_entry(
			step.reference_document,
			() => {
				if (frappe.get_route_str() != current_route) {
					let success_dialog = frappe.msgprint({
						message: __("Let's take you back to onboarding"),
						title: __("Document Saved"),
						primary_action: {
							action: () => {
								success_dialog.hide();
								frappe.set_route(current_route).then(() => {
									this.mark_complete(step);
								});
							},
							label: __("Continue"),
						},
					});

					frappe.msg_dialog.custom_onhide = () => {
						frappe.set_route(current_route).then(() => {
							this.mark_complete(step);
						});
					};
				} else {
					frappe.show_alert(
						__("Document Saved") + "<br>" + __("Let us continue with the onboarding")
					);
					this.mark_complete(step);
				}
			},
			null,
			null,
			true
		);
	}

	mark_complete(step) {
		this.update_step_status(step, "is_complete");
	}

	skip_step(step) {
		this.update_step_status(step, "is_skipped");
	}

	update_step_status(step, field) {
		// a step done means the hooks set up for it are spent
		frappe.route_hooks = {};

		return frappe
			.call("frappe.desk.desktop.update_onboarding_step", {
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

	// The first unfinished step after `after`, wrapping round; the first unfinished one overall
	// when nothing is given.
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
					frappe.telemetry.capture(
						"dismissed_" + frappe.scrub(this.title),
						"frappe_onboarding"
					);
				},
			})
		);
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
