frappe.ui.OnboardingTour = class OnboardingTour {
	constructor() {
		this.driver_steps = [];
		this.last_step_saved = null;
		this.last_element_clicked = null;
	}

	init_driver() {
		this.driver = new frappe.Driver({
			className: "frappe-driver",
			allowClose: false,
			padding: 10,
			overlayClickNext: false,
			keyboardControl: true,
			nextBtnText: __("Next"),
			prevBtnText: __("Previous"),
			doneBtnText: __("Done"),
			closeBtnText: __("Close"),
			opacity: 0.5,
			onHighlighted: (step) => {
				frappe.ui.next_form_tour = step.options.step_info?.next_form_tour;
				const wait_for_node = setInterval(() => {
					if (!step.popover.node) return;
					if (step.options.step_info?.offset_x) {
						step.popover.node.style.left = `${
							step.popover.node.offsetLeft + step.options.step_info.offset_x
						}px`;
					}
					if (step.options.step_info?.offset_y) {
						step.popover.node.style.top = `${
							step.popover.node.offsetTop + step.options.step_info.offset_y
						}px`;
					}
					if (step.popover.node.offsetLeft < 0) {
						step.popover.node.style.minWidth = "200px";
						step.popover.node.style.maxWidth = `${
							350 + step.popover.node.offsetLeft
						}px`;
						step.popover.node.style.left = "0px";
					}
					if (step.popover.closeBtnNode) {
						step.popover.closeBtnNode.onclick = () => {
							this.on_finish && this.on_finish();
							!frappe.boot.user.onboarding_status[this.tour.name] &&
								(frappe.boot.user.onboarding_status[this.tour.name] = {});
							frappe.boot.user.onboarding_status[this.tour.name].is_complete = true;
							if (!this.driver.hasNextStep()) {
								frappe.boot.user.onboarding_status[
									this.tour.name
								].all_steps_completed = true;
							}

							frappe.call({
								method: "frappe.desk.doctype.form_tour.form_tour.update_user_status",
								args: {
									value: JSON.stringify(frappe.boot.user.onboarding_status),
									step: JSON.stringify(step.options.step_info),
								},
							});
						};
					}
					clearInterval(wait_for_node);
				}, 300);

				// focus on first input.
				// TODO : later add option to select which input to focus as well.
				const $input = $(step.node).find("input").get(0);
				if ($input) frappe.utils.sleep(200).then(() => $input.focus());
			},
		});
	}

	async init({ tour_name, start_step }) {
		this.tour = await frappe.db.get_doc("Form Tour", tour_name);
		this.init_driver();
		this.build_steps();
		this.update_driver_steps();
		if (!this.tour.track_steps) {
			start_step = 0;
		}
		this.start(start_step);
	}

	build_steps() {
		this.driver_steps = [];
		this.tour.steps.forEach((step) => {
			const on_next = async (el) => {
				const step_index = this.driver.steps.indexOf(el);
				if (step_index == -1 || this.last_step_saved?.name == step.name) return;
				frappe.boot.user.onboarding_status[this.tour.name] = {
					steps_complete: step_index,
				};
				if (!this.driver.hasNextStep()) {
					this.on_finish && this.on_finish();
					frappe.boot.user.onboarding_status[this.tour.name].is_complete = true;
				}
				this.last_step_saved = step;
				frappe.call({
					method: "frappe.desk.doctype.form_tour.form_tour.update_user_status",
					args: {
						value: JSON.stringify(frappe.boot.user.onboarding_status),
						step: JSON.stringify(step),
					},
				});
			};
			const driver_step = this.get_step(step, on_next);
			driver_step.element && this.driver_steps.push(driver_step);
		});
	}

	get_step(step_info, on_next) {
		const {
			name,
			element_selector,
			title,
			description,
			ondemand_description,
			position,
			parent_element_selector,
			hide_buttons,
			next_on_click,
			popover_element,
			modal_trigger,
		} = step_info;
		let element = cur_page?.page.querySelector(element_selector);
		!element && (element = document.querySelector(element_selector));
		if (parent_element_selector) {
			element = element.closest(parent_element_selector);
		}
		if (element && (next_on_click || hide_buttons || modal_trigger)) {
			$(element).on("click", () => {
				if (
					!this.driver.getHighlightedElement() ||
					this.driver.getHighlightedElement().node.id?.startsWith("popover")
				)
					return;

				if (
					modal_trigger &&
					(!this.last_element_clicked ||
						new Date().getTime() - new Date(this.last_element_clicked).getTime() >
							1000)
				) {
					this.last_element_clicked = new Date().getTime();
					this.handle_modal_steps(this.driver.currentStep, title, ondemand_description);
					return;
				}

				if (!popover_element) {
					on_next(this.driver.getHighlightedElement());
					this.driver.moveNext();
					this.driver.overlay.refresh();
				}

				if (!this.driver.getHighlightedElement()) return;
				on_next(this.driver.getHighlightedElement());
				let popover = this.driver
					.getHighlightedElement()
					.node.getAttribute("aria-describedby")
					? this.driver.getHighlightedElement().node
					: this.driver
							.getHighlightedElement()
							.node.querySelector('[aria-describedby^="popover"]');

				if (!popover) return;

				let popover_id = popover.getAttribute("aria-describedby");
				let step_index = this.driver.steps.indexOf(this.driver.getHighlightedElement());

				if (this.driver_steps[step_index + 1]?.element.id == popover_id) return;

				this.driver_steps = this.driver_steps.filter(
					(step) => !step.element.id?.startsWith("popover")
				);

				let new_step = { ...this.driver_steps[step_index] };
				new_step.element = document.getElementById(popover_id);
				new_step.showButtons = false;
				ondemand_description && (new_step.popover.description = ondemand_description);

				this.driver_steps.splice(this.driver.currentStep + 1, 0, new_step);
				this.update_driver_steps();
				this.driver.moveNext();
				this.driver.overlay.refresh();

				$(popover).one("hide.bs.popover", (e) => {
					this.driver_steps.splice(this.driver.currentStep, 1);
					this.driver_steps[this.driver.currentStep - 1].showButtons = true;
					new_step.popover.description = description;
					this.update_driver_steps();
					this.driver.movePrevious();
					this.driver.overlay.refresh();
				});
			});
		}

		let showButtons = true;
		if (popover_element || hide_buttons) {
			showButtons = false;
		}
		return {
			element,
			name,
			popover: {
				title,
				description,
				position: frappe.router.slug(position || "Bottom"),
			},
			onNext: on_next,
			step_info: step_info,
			showButtons,
		};
	}

	update_driver_steps(steps = []) {
		if (steps.length == 0) {
			steps = this.driver_steps;
		}
		this.driver.defineSteps(steps);
	}

	start(idx = 0) {
		if (this.driver_steps.length == 0) {
			return;
		}
		this.driver.start(idx);
	}

	handle_modal_steps(step, title, description) {
		setTimeout(() => {
			const modal_element = $(".modal-content");
			const attach_dialog_step = {
				element: modal_element[0],
				allowClose: false,
				overlayClickNext: false,
				popover: {
					title,
					description,
					position: "left-center",
					doneBtnText: __("Next"),
				},
			};
			this.driver_steps.splice(step + 1, 0, attach_dialog_step);
			this.update_driver_steps(); // need to define again, since driver.js only considers steps which are inside DOM
			this.driver.reset();
			this.driver.start(step + 1);
			this.driver.overlay.refresh();
			modal_element.closest(".modal").one("hide.bs.modal", () => {
				this.driver_steps.splice(this.driver.currentStep, 1);
				this.update_driver_steps();
				this.driver.movePrevious();
				this.driver.moveNext();
				this.driver.overlay.refresh();
			});
		}, 500);
	}
};

frappe.ui.init_onboarding_tour = () => {
	// As of now Tours are only for desktop as it is annoying on mobile.
	// Also lot of elements are hidden on mobile so until we find a better way to do it.
	if (!window.matchMedia("(min-device-width: 992px)").matches) return;

	typeof frappe.boot.onboarding_tours == "undefined" && frappe.boot.onboarding_tours == [];
	typeof frappe.boot.user.onboarding_status == "undefined" &&
		frappe.boot.user.onboarding_status == {};
	let route = frappe.router.current_route;
	if (route[0] === "") return;

	let tour_name;
	let matching_tours = [];
	let start_step;
	if (route[0] == "query-report") {
		route = ["List", route[1], "Report"];
	}
	if (route[0] != "dashboard-view") {
		frappe.boot.onboarding_tours &&
			frappe.boot.onboarding_tours.forEach((tour) => {
				let tour_route = tour[1];
				length = Math.min(route.length, tour_route.length);
				if (length >= 1 && route[0] != tour_route[0]) return;
				if (length >= 2 && tour_route[1] != "*" && route[1] != tour_route[1]) return;
				if (
					length >= 3 &&
					["*", "new-*"].indexOf(tour_route[2]) == -1 &&
					route[2] != tour_route[2]
				)
					return;
				matching_tours.push(tour);
			});
	}
	matching_tours = matching_tours.filter((tour) => {
		if (frappe.boot.user.onboarding_status[tour[0]]?.is_complete == true) return false;
		return true;
	});
	matching_tours = matching_tours.map((tour) => {
		if (frappe.boot.user.onboarding_status[tour[0]]?.steps_complete != undefined) {
			tour.push(frappe.boot.user.onboarding_status[tour[0]].steps_complete);
		}
		return tour;
	});
	if (matching_tours.length == 0) return;
	let current_tour = matching_tours.find(
		(tour) => tour[0] == frappe.ui.currentTourInstance?.tour?.name
	);
	let next_tour = matching_tours.find((tour) => tour[0] == frappe.ui.next_form_tour);
	if (current_tour) {
		tour_name = current_tour[0];
		start_step = current_tour.at(-1);
		if (typeof start_step != "number") {
			start_step = 0;
		}
	} else if (next_tour) {
		tour_name = next_tour[0];
		start_step = next_tour.at(-1);
		if (typeof start_step != "number") {
			start_step = 0;
		} else {
			start_step += 1;
		}
		frappe.ui.next_form_tour = undefined;
	} else {
		tour_name = matching_tours[0][0];
		start_step = matching_tours[0].at(-1);
		if (typeof start_step != "number") {
			start_step = 0;
		} else {
			start_step += 1;
		}
	}
	if (!tour_name) return;
	if (frappe.ui.currentTourInstance?.driver) {
		frappe.ui.currentTourInstance.driver_steps = [];
		frappe.ui.currentTourInstance.driver.reset(true);
		frappe.ui.currentTourInstance.update_driver_steps();
	}
	const tour = (frappe.ui.currentTourInstance = new frappe.ui.OnboardingTour());
	// wait for workspace and/or data to load.
	const wait_for_data = setInterval(() => {
		if (cur_page?.page.querySelector(".workspace-sidebar-skeleton")) return;
		if (cur_page?.page.querySelector(".workspace-skeleton")) return;
		if (document.body.getAttribute("data-ajax-state") === "complete") {
			frappe.utils.sleep(500).then(() => {
				tour.init({
					tour_name,
					start_step,
				});
				clearInterval(wait_for_data);
			});
		}
	}, 100);
};

frappe.router.on("change", () => {
	frappe.ui.init_onboarding_tour();
});
