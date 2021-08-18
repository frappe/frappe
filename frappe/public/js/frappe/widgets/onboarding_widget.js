import Widget from "./base_widget.js";

frappe.provide("frappe.utils");

export default class OnboardingWidget extends Widget {
	make_body() {
		this.steps_wrapper = $(`<div class="onboarding-steps-wrapper"></div>`).appendTo(this.body);
		this.step_preview = $(`<div class="onboarding-step-preview">
			<div class="onboarding-step-body"></div>
			<div class="onboarding-step-footer"></div>
		</div>`).appendTo(this.body);

		this.step_body = this.step_preview.find(".onboarding-step-body");
		this.step_footer = this.step_preview.find(".onboarding-step-footer");

		this.steps.forEach((step, index) => {
			this.add_step(step, index);
		});

		this.show_step(this.steps[0]);
	}

	add_step(step, index) {
		let status = 'pending';

		if (step.is_skipped) status = "skipped";
		if (step.is_complete) status = "complete";

		let $step = $(`<a class="onboarding-step ${status}">
				<div class="step-title">
					<div class="step-index step-pending">${__(index + 1)}</div>
					<div class="step-index step-skipped">${frappe.utils.icon('tick', 'xs')}</div>
					<div class="step-index step-complete">${frappe.utils.icon('tick', 'xs')}</div>
					<div>${__(step.title)}</div>
				</div>
			</a>`);

		step.$step = $step;

		// Add skip button
		if (!step.is_complete && !step.is_skipped) {
			let skip_html = $(
				`<div class="step-skip">${__('Skip')}</div>`
			);

			skip_html.appendTo($step);
			skip_html.on("click", () => {
				this.skip_step(step);
				event.stopPropagation();
			});
		}
		$step.on("click", () => this.show_step(step));
		$step.appendTo(this.steps_wrapper);

		return $step;
	}

	show_step(step) {
		this.active_step && this.active_step.$step.removeClass("active");

		step.$step.addClass("active");
		this.active_step = step;

		let actions = {
			"Watch Video": (step) => this.show_video(step),
			"Create Entry": (step) => {
				if (step.is_complete) {
					frappe.set_route(`/app/List/${step.reference_document}`);
				} else {
					if (step.show_full_form) {
						this.create_entry(step);
					} else {
						this.show_quick_entry(step);
					}
				}
			},
			"Show Form Tour": (step) => this.show_form_tour(step),
			"Update Settings": (step) => this.update_settings(step),
			"View Report": (step) => this.open_report(step),
			"Go to Page": (step) => this.go_to_page(step),
		};

		const toggle_content = () => {
			this.step_body.empty();
			this.step_footer.empty();

			this.step_body.html(
				step.description ?
					frappe.markdown(step.description)
					: `<h1>${step.title}</h1>`
			);

			if (step.intro_video_url) {
				$(`<button class="btn btn-primary btn-sm">${__('Watch Tutorial')}</button>`)
					.appendTo(this.step_footer)
					.on('click', toggle_video);
			} else {
				$(`<button class="btn btn-primary btn-sm">${__(step.action_label || step.action)}</button>`)
					.appendTo(this.step_footer)
					.on('click', () => actions[step.action](step));
			}
		};

		const toggle_video = () => {
			this.step_body.empty();
			this.step_footer.empty();

			const video = $(`<div class="video-player" data-plyr-provider="youtube" data-plyr-embed-id="${step.intro_video_url}"></div>`);
			video.appendTo(this.step_body);
			let plyr = new frappe.Plyr(video[0], {
				hideControls: true,
				resetOnEnd: true,
			});

			$(`<button class="btn btn-primary btn-sm">${__(step.action_label || step.action)}</button>`)
				.appendTo(this.step_footer)
				.on('click', () => {
					plyr.pause();
					actions[step.action](step);
				});

			// Fire only once, on hashchange
			$(window).one('hashchange', () => {
				plyr.pause();
			});

			$(`<button class="btn btn-secondary ml-2 btn-sm">${__('Back')}</button>`)
				.appendTo(this.step_footer)
				.on('click', toggle_content);
		};

		toggle_content();
		// toggle_video();
	}

	go_to_page(step) {
		this.mark_complete(step);
		frappe.set_route(step.path).then(() => {
			let message = step.callback_message || __("You can continue with the onboarding after exploring this page");
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
			frm.show_tour(() => {
				let msg_dialog = frappe.msgprint({
					message: __("Let's take you back to onboarding"),
					title: __("Great Job"),
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
			});
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
				args.title = __("Looks Great");
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
				args.title = __("Oops");
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

	create_entry(step) {
		let current_route = frappe.get_route();

		frappe.route_hooks = {};
		frappe.route_hooks.after_load = (frm) => {
			frm.show_tour(() => {
				frappe.msgprint({
					message: __("Awesome, now try making an entry yourself"),
					title: __("Great"),
				});
			});
		};

		let callback = () => {
			frappe.msgprint({
				message: __("You're doing great, let's take you back to the onboarding page."),
				title: __("Good Work 🎉"),
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
					title: __("Great")
				});
			};
			frappe.route_hooks.after_submit = callback;
		} else {
			frappe.route_hooks.after_save = callback;
		}

		frappe.set_route('Form', step.reference_document, 'new');
	}

	show_quick_entry(step) {
		let current_route = frappe.get_route_str();
		frappe.ui.form.make_quick_entry(
			step.reference_document,
			() => {
				if (frappe.get_route_str() != current_route) {
					let success_dialog = frappe.msgprint({
						message: __("Let's take you back to onboarding"),
						title: __("Looks Great"),
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
					frappe.msgprint({
						message: __("Let us continue with the onboarding"),
						title: __("Looks Great")
					});
					this.mark_complete(step);
				}
			},
			null,
			null,
			true
		);
	}

	show_video(step) {
		frappe.help.show_video(step.video_url, step.title);
		this.mark_complete(step);
	}

	mark_complete(step) {
		let $step = step.$step;

		let callback = () => {
			step.is_complete = true;
			$step.removeClass("skipped");
			$step.addClass("complete");
		};

		this.update_step_status(step, "is_complete", 1, callback);
	}

	skip_step(step) {
		let $step = step.$step;

		let callback = () => {
			step.is_skipped = true;
			$step.removeClass("complete");
			$step.removeClass("pending");
			$step.addClass("skipped");
		};

		this.update_step_status(step, "is_skipped", 1, callback);
	}

	update_step_status(step, status, value, callback) {
		let icon_class = {
			is_complete: "complete",
			is_skipped: "skipped",
		};
		//  Clear any hooks
		frappe.route_hooks = {};

		frappe
			.call("frappe.desk.desktop.update_onboarding_step", {
				name: step.name,
				field: status,
				value: value,
			})
			.then(() => {
				callback();

				step.$step
					.removeClass("pending")
					.removeClass("complete")
					.removeClass("skipped")
					.addClass(icon_class[status]);

				let pending = this.steps.filter((step) => {
					return !(step.is_complete || step.is_skipped);
				});

				if (pending.length == 0) {
					this.show_success();
				}
			});
	}

	show_success() {
		let success_message = this.success || __("You seem good to go!");
		let success_state_image =
			this.success_state_image ||
			"/assets/frappe/images/ui-states/success-color.png";
		let documentation = "";
		if (this.docs_url) {
			documentation = __(
				'Congratulations on completing the module setup. If you want to learn more you can refer to the documentation <a target="_blank" href="{0}">here</a>.',
				[this.docs_url]
			);
		}

		let success = $(`<div class="text-center onboarding-success">
					<img src="${success_state_image}" alt="Success State" class="zoom-in success-state">
					<h3>${success_message}</h3>
					<div class="text-muted">${documentation}</div>
					<button class="btn btn-primary btn-sm">${__('Continue')}</button>
			</div>
		`);

		success.find('.btn').on('click', () => this.delete());

		this.step_preview.empty();
		success.appendTo(this.step_preview);
	}

	set_body() {
		this.widget.addClass("onboarding-widget-box");
		if (this.is_dismissed()) {
			this.widget.hide();
		} else {
			this.make_body();
		}
	}

	is_dismissed() {
		let dismissed = JSON.parse(
			localStorage.getItem("dismissed-onboarding") || "{}"
		);
		if (Object.keys(dismissed).includes(this.label)) {
			let last_hidden = new Date(dismissed[this.label]);
			let today = new Date();
			let diff = frappe.datetime.get_hour_diff(today, last_hidden);
			return diff < 24;
		}
		return false;
	}

	set_actions() {
		this.action_area.empty();
		const dismiss = $(
			`<div class="small" style="cursor:pointer;">${__('Dismiss', null, 'Stop showing the onboarding widget.')}</div>`
		);
		dismiss.on("click", () => {
			let dismissed = JSON.parse(
				localStorage.getItem("dismissed-onboarding") || "{}"
			);
			dismissed[this.label] = frappe.datetime.now_datetime();

			localStorage.setItem(
				"dismissed-onboarding",
				JSON.stringify(dismissed)
			);
			this.delete();
		});
		dismiss.appendTo(this.action_area);
	}
}
