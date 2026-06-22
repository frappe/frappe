frappe.ui.form.FormTour = class FormTour {
	constructor({ frm }) {
		this.frm = frm;
		this.driver_steps = [];
	}

	init_driver() {
		this.driver = new frappe.Driver({
			className: "frappe-driver",
			allowClose: false,
			padding: 10,
			overlayClickNext: true,
			keyboardControl: true,
			nextBtnText: __("Next"),
			prevBtnText: __("Previous"),
			doneBtnText: __("Done"),
			closeBtnText: __("Close"),
			opacity: 0.25,
			onHighlighted: (step) => {
				// if last step is to save, then attach a listener to save button
				if (step.options.is_save_step) {
					$(step.options.element).one("click", () => this.driver.reset());
					this.driver.overlay.refresh();
				}

				// focus on input
				const $input = $(step.node).find("input").get(0);
				if ($input) frappe.utils.sleep(200).then(() => $input.focus());
			},
		});

		frappe.router.on("change", () => this.driver.reset());
		this.frm.layout.sections.forEach((section) => section.collapse(false));
	}

	async init({ tour_name, on_finish }) {
		if (tour_name) {
			this.tour = await frappe.db.get_doc("Form Tour", tour_name);
		} else {
			const doctype_tour_exists = await frappe.db.exists("Form Tour", this.frm.doctype);
			if (doctype_tour_exists) {
				this.tour = await frappe.db.get_doc("Form Tour", this.frm.doctype);
			} else {
				this.tour = { steps: frappe.tour[this.frm.doctype] };
			}
		}

		if (!this.tour.steps) return;

		if (on_finish) this.on_finish = on_finish;

		this.init_driver();
		if (this.tour.include_name_field) this.include_name_field();
		this.build_steps();
		this.update_driver_steps();
	}

	include_name_field() {
		const name_step = {
			description: __("Enter a name for this {0}", [this.frm.doctype]),
			fieldname: "__newname",
			title: __("Document Name"),
			position: "right",
			is_table_field: 0,
		};
		this.tour.steps.unshift(name_step);
	}

	build_steps() {
		this.driver_steps = [];
		this.tour.steps.forEach((step) => {
			const on_next = () => {
				if (!this.is_next_condition_satisfied(step)) {
					this.driver.preventMove();
				}

				if (!this.driver.hasNextStep()) {
					this.on_finish && this.on_finish();
				}
				let field = this.get_next_step()?.options.element.fieldobj;
				if (field?.tab && !field.tab.is_active()) {
					field.tab.set_active();
					this.driver.reset(true);
					frappe.utils.sleep(200).then(() => {
						this.start(step.idx);
						this.driver.overlay.refresh();
					});
				}
			};
			const on_prev = () => {
				if (!this.driver.hasPreviousStep()) return;
				let field =
					this.driver.steps[this.driver.currentStep - 1]?.options.element.fieldobj;
				if (field?.tab && !field.tab.is_active()) {
					field.tab.set_active();
					this.driver.reset(true);
					frappe.utils.sleep(200).then(() => {
						this.start(step.idx - 2);
						this.driver.overlay.refresh();
					});
				}
			};

			const driver_step = this.get_step(step, on_next, on_prev);
			this.driver_steps.push(driver_step);

			if (step.fieldtype == "Table") this.handle_table_step(step);
			if (step.is_table_field) this.handle_child_table_step(step);
			if (step.fieldtype == "Attach Image") this.handle_attach_image_steps(step);
		});

		if (this.tour.save_on_complete && this.frm.is_dirty()) {
			this.add_step_to_save();
		}
	}

	is_next_condition_satisfied(step) {
		const form = step.is_table_field ? this.frm.cur_grid.grid_form : this.frm;
		return form.layout.evaluate_depends_on_value(step.next_step_condition || true);
	}

	get_step(step_info, on_next, on_prev) {
		const { name, fieldname, title, description, position, is_table_field } = step_info;
		let element = `.frappe-control[data-fieldname='${fieldname}']`;

		const field = this.frm.get_field(fieldname);
		if (field) {
			// wrapper for section breaks returns in a list
			element = field.wrapper[0] ? field.wrapper[0] : field.wrapper;
		}

		if (is_table_field) {
			// TODO: fix wrapper for grid sections
			element = `.grid-row-open .frappe-control[data-fieldname='${fieldname}']`;
		}

		return {
			element,
			name,
			popover: {
				title: __(title),
				description: __(description),
				position: frappe.router.slug(position || "Bottom"),
			},
			onNext: on_next,
			onPrevious: on_prev,
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

	get_next_step() {
		// returns the next step only if driver is active
		if (this.driver.isActivated & this.driver.hasNextStep()) {
			const current_step = this.driver.currentStep;
			return this.driver.steps[current_step + 1];
		}
		return;
	}

	handle_table_step(step_info) {
		const is_last_step = step_info.idx == this.tour.steps.length;

		if (!is_last_step) {
			// if next step field is inside currently highlighted table field
			// then check if there is a row -> if not, then prompt to add row
			// then edit the first row and hightlight next step

			const curr_step = step_info;
			const next_step = this.tour.steps[curr_step.idx];
			const is_next_field_in_curr_table = next_step.parent_fieldname == curr_step.fieldname;

			if (!is_next_field_in_curr_table) return;

			const rows = this.frm.doc[curr_step.fieldname];
			const table_has_rows = rows && rows.length > 0;
			if (table_has_rows) {
				// table already has rows
				// then just edit the first one on next step
				const curr_driver_step = this.driver_steps.find((s) => s.name == curr_step.name);
				curr_driver_step.onNext = () => {
					if (this.is_next_condition_satisfied(curr_step)) {
						this.expand_row_and_proceed(curr_step, curr_step.idx);
					} else {
						this.driver.preventMove();
					}
				};
				this.update_driver_steps();
			} else {
				this.add_new_row_step(curr_step);
			}
		}
	}

	add_new_row_step(step) {
		const $add_row = `.frappe-control[data-fieldname='${step.fieldname}'] .grid-add-row`;
		const add_row_step = {
			element: $add_row,
			popover: { title: __("Add a Row"), description: "" },
			onNext: () => {
				if (!cur_frm.cur_grid) {
					this.driver.preventMove();
				}
			},
		};
		this.driver_steps.push(add_row_step);

		// setup a listener on add row button
		// so, once the row is added, move to next step automatically
		$($add_row).one("click", () => {
			this.expand_row_and_proceed(step, step.idx + 1); // +1 since add row step is added
		});
	}

	expand_row_and_proceed(step, start_from) {
		this.open_first_row_of(step.fieldname);
		this.update_driver_steps(); // need to define again, since driver.js only considers steps which are inside DOM
		frappe.utils.sleep(300).then(() => this.driver.start(start_from));
	}

	open_first_row_of(fieldname) {
		this.frm.fields_dict[fieldname].grid.grid_rows[0].toggle_view();

		// setup a listener on close row button
		// so, once the row is closed, move to next step automatically
		const $close_row = ".grid-row-open .grid-collapse-row";
		$($close_row).one("click", () => {
			const next_step = this.get_next_step();
			const next_element = next_step.options.is_save_step ? null : next_step.node;

			frappe.utils.scroll_to(next_element, true, 150, null, () => {
				this.driver.moveNext();
				frappe.flags.disable_auto_scroll = false;
			});
			frappe.flags.disable_auto_scroll = true;
		});
	}

	handle_child_table_step(step_info) {
		const is_last_step = step_info.idx == this.tour.steps.length;

		if (!is_last_step) {
			const curr_step = step_info;
			const next_step = this.tour.steps[curr_step.idx];
			const field = this.frm.get_field(next_step.fieldname);

			if (!field) return;

			// next step highlights parent field
			// so, add a step to prompt user to collapse grid form
			this.add_collapse_row_step();
		} else if (this.tour.save_on_complete) {
			// if last step & save on complete is checked
			// add a step to prompt user to collapse grid form
			// to be able to save as a last step
			this.add_collapse_row_step();
		}
	}

	add_collapse_row_step() {
		const $close_row = ".grid-row-open .grid-collapse-row";
		const close_row_step = {
			element: $close_row,
			popover: { title: __("Collapse"), description: "", position: "left" },
			onNext: () => {
				if (cur_frm.cur_grid) {
					this.driver.preventMove();
				}
			},
		};
		this.driver_steps.push(close_row_step);
	}

	add_step_to_save() {
		const page_id = `[id="page-${this.frm.doctype}"]`;
		const $save_btn = `${page_id} .standard-actions .primary-action`;
		const save_step = {
			element: $save_btn,
			is_save_step: true,
			allowClose: false,
			overlayClickNext: false,
			popover: {
				title: __("Save the document."),
				description: "",
				position: "left",
				showButtons: false,
			},
			onNext: () => {
				this.frm.save();
			},
		};
		this.driver_steps.push(save_step);
		frappe.ui.form.on(
			this.frm.doctype,
			"after_save",
			() => this.on_finish && this.on_finish()
		);
	}

	handle_attach_image_steps() {
		$(".btn-attach").one("click", () => {
			setTimeout(() => {
				const modal_element = $(".file-uploader").closest(".modal-content");
				const attach_dialog_step = {
					element: modal_element[0],
					allowClose: false,
					overlayClickNext: false,
					popover: {
						title: __("Select an Image"),
						description: "",
						position: "left",
						doneBtnText: __("Next"),
					},
				};

				this.driver_steps.splice(this.driver.currentStep + 1, 0, attach_dialog_step);
				this.update_driver_steps(); // need to define again, since driver.js only considers steps which are inside DOM
				this.driver.moveNext();
				this.driver.overlay.refresh();

				modal_element.closest(".modal").on("hidden.bs.modal", () => {
					this.driver.moveNext();
				});
			}, 500);
		});
	}
};
