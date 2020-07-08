import Widget from "./base_widget.js";
import { generate_route } from "./utils";

export default class OnboardingWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	make_body() {
		this.steps.forEach((step) => {
			this.add_step(step);
		});
	}

	add_step(step) {
		// Make Step
		let status = "";
		let icon_class = "fa-circle-o";

		if (step.is_skipped) {
			status = "skipped";
			icon_class = "fa-check-circle-o";
		}

		if (step.is_complete) {
			status = "complete";
			icon_class = "fa-check-circle-o";
		}

		let $step = $(`<div class="onboarding-step ${status}">
				<i class="fa ${icon_class}" aria-hidden="true" title="${status}"></i>
				<span id="title">${step.title}</span>
			</div>`);

		step.$step = $step;

		// Add skip button
		if (!step.is_mandatory && !step.is_complete) {
			let skip_html = $(
				`<span class="ml-5 small text-muted step-skip">Skip</span>`
			);

			skip_html.appendTo($step);
			skip_html.on("click", () => {
				this.skip_step(step);
				event.stopPropagation();
			});
		}

		// Setup actions
		let actions = {
			"Watch Video": () => this.show_video(step),
			"Create Entry": () => {
				if (step.is_complete) {
					frappe.set_route(`#List/${step.reference_document}`);
				} else {
					if (step.show_full_form) {
						this.create_entry(step);
					} else {
						this.show_quick_entry(step);
					}
				}
			},
			"Show Form Tour": () => this.show_form_tour(step),
			"Update Settings": () => this.update_settings(step),
			"View Report": () => this.open_report(step),
			"Go to Page": () => this.go_to_page(step),
		};

		$step.find("#title").on("click", actions[step.action]);

		$step.appendTo(this.body);
		return $step;
	}

	go_to_page(step) {
		frappe.set_route(step.path).then(() => {
			if (step.callback_message) {
				let msg_dialog = frappe.msgprint({
					message: __(step.callback_message),
					title: __(step.callback_title),
					primary_action: {
						action: () => {
							msg_dialog.hide();
						},
						label: () => __("Continue"),
					},
					wide: true,
				});
			}
		});
	}

	open_report(step) {
		let route = generate_route({
			name: step.reference_report,
			type: "report",
			is_query_report: ["Query Report", "Script Report"].includes(
				step.report_type
			),
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
			route = `Form/${step.reference_document}`;
		} else {
			route = `Form/${step.reference_document}/${__('New')} ${__(step.reference_document)}`;
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

				if (!step.is_mandatory) {
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
				}

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

		frappe.set_route(`Form/${step.reference_document}/${__('New')} ${__(step.reference_document)}`);
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
						message: __("You may continue with onboarding"),
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
			$step.addClass("skipped");
		};

		this.update_step_status(step, "is_skipped", 1, callback);
	}

	update_step_status(step, status, value, callback) {
		let icon_class = {
			is_complete: "fa-check-circle-o",
			is_skipped: "fa-check-circle-o",
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

				let icon = step.$step.find("i.fa");
				icon.removeClass();
				icon.addClass("fa");
				icon.addClass(icon_class[status]);

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
				'Congratulations on completing the module setup. If you want to learn more you can refer to the documentation <a href="{0}">here</a>.',
				[this.docs_url]
			);
		}

		let success = $(`<div class="text-center onboarding-success">
					<img src="${success_state_image}" alt="Success State" class="zoomIn success-state">
					<h3>${success_message}</h3>
					<div class="text-muted">${documentation}</div>
			</div>
		`);

		if (!this.success_dialog) {
			this.success_dialog = new frappe.ui.Dialog({
				primary_action: () => {
					this.success_dialog.hide();
					// Wait for modal to close before removing widget
					setTimeout(() => {
						this.delete();
					}, 300);
				},
				primary_action_label: __("Continue"),
			});

			this.success_dialog.set_title(__("Onboarding Complete"));
			this.success_dialog.header
				.find(".indicator")
				.removeClass("hidden")
				.addClass("green");

			success.appendTo(this.success_dialog.$body);
			this.success_dialog.show();
		}
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

	set_title(title) {
		super.set_title(title);
		if (this.subtitle) {
			let subtitle = $(
				`<div class="widget-subtitle">${this.subtitle}</div>`
			);
			subtitle.appendTo(this.title_field);
		}
	}

	set_actions() {
		this.action_area.empty();
		const dismiss = $(
			`<div class="small" style="cursor:pointer;">Dismiss</div>`
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
