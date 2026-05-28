import Awesomplete from "awesomplete";

frappe.ui.form.ControlMultiSelectList = class ControlMultiSelectList extends (
	frappe.ui.form.ControlData
) {
	static trigger_change_on_input_event = false;
	make_input() {
		let template = `
			<div class="multiselect-list dropdown">
				<input type="text" class="form-control input-xs" autocomplete="off">
				<ul class="dropdown-menu">
					<div class="selectable-items">
					</div>
					<li class="d-flex justify-content-end">
						<button class="btn btn-secondary btn-xs select-all-options text-nowrap mr-2">
							${__("Select All")}
						</button>
						<button class="btn btn-primary btn-xs clear-selections text-nowrap">
							${__("Clear All")}
    					</button>
					</li>
				</ul>
			</div>
		`;

		this.$list_wrapper = $(template);
		this.$input = this.$list_wrapper.find("> input");
		this.input = this.$input.get(0);
		this.has_input = true;
		this.$list_wrapper.prependTo(this.input_area);

		this.$list_wrapper.on("click", ".dropdown-menu", (e) => {
			e.stopPropagation();
		});
		this.$list_wrapper.on("click", ".clear-selections", () => {
			this.clear_all_selections();
		});
		this.$list_wrapper.on("click", ".select-all-options", () => {
			this.select_all_options();
		});
		this.$list_wrapper.on("click", ".selectable-item", (e) => {
			let $target = $(e.currentTarget);
			this.toggle_select_item($target);
		});

		this.$input.on(
			"input",
			frappe.utils.debounce(() => {
				this.set_options().then(() => {
					let txt = this.$input.val() || "";
					if (txt) {
						let filtered = this._options.filter((opt) => {
							return (
								Awesomplete.FILTER_CONTAINS(opt.label, txt) ||
								Awesomplete.FILTER_CONTAINS(opt.value, txt) ||
								Awesomplete.FILTER_CONTAINS(opt.description, txt)
							);
						});
						this.set_selectable_items(this.merge_selected(filtered));
					} else {
						this.set_selectable_items(this.merge_selected(this._options));
					}
				});
			}, 300)
		);

		this.$input.on("keydown", (e) => {
			if (e.key === "ArrowDown") {
				e.preventDefault();
				this.highlight_item(1);
			} else if (e.key === "ArrowUp") {
				e.preventDefault();
				this.highlight_item(-1);
			} else if (e.key === "Enter" || e.key === "Tab") {
				if (this._$last_highlighted) {
					e.preventDefault();
					this.toggle_select_item(this._$last_highlighted);
					return false;
				}
			} else if (e.key === "Backspace" && !this.$input.val()) {
				// remove last selected value
				if (this.values.length) {
					let removed = this.values[this.values.length - 1];
					this.values = this.values.slice(0, -1);
					this._selected_values = (this._selected_values || []).filter(
						(opt) => opt.value !== removed
					);
					this.parse_validate_and_set_in_model("");
					this.refresh_selectable_items();
				}
			}
		});

		this.$input.on("focus", () => {
			this._focused = true;
			this.$input.val("");
			this.$input.attr("placeholder", this.df.placeholder || __("Type to search..."));
			this.open_dropdown();
		});

		this.$input.on("blur", () => {
			this._focused = false;
			// delay to allow click events on dropdown items
			setTimeout(() => {
				if (!this._focused) {
					this.close_dropdown();
					this.show_summary();
				}
			}, 200);
		});

		this.setup_paste_handler();
		this.set_input_attributes();
		this.values = [];
		this._options = [];
		this._selected_values = [];
		this.highlighted = -1;
	}

	set_formatted_input() {
		// Prevent parent ControlData from overwriting our summary display
		if (!this._focused) {
			this.show_summary();
		}
	}

	set_input(value) {
		// When called from report filter restore (set_filters/set_route_filters),
		// value may be an array - restore it into this.values
		if (Array.isArray(value)) {
			this.values = value;
			this.values.forEach((v) => this.update_selected_values(v));
		}
		this.show_summary();
	}

	merge_selected(options) {
		// Ensure selected values always appear in dropdown even if
		// the server/get_data didn't return them
		let option_values = new Set(options.map((o) => o.value));
		let merged = options.slice();
		for (let sel of this._selected_values || []) {
			if (this.values.includes(sel.value) && !option_values.has(sel.value)) {
				merged.push(sel);
			}
		}
		return merged;
	}

	setup_paste_handler() {
		this.$input.on("paste", (e) => {
			const clipboard_data = (e.originalEvent || e).clipboardData;
			if (!clipboard_data) return;

			const pasted = clipboard_data.getData("text");
			if (!pasted) return;

			// Handle Excel paste (newline/tab separated values)
			if (!pasted.includes("\n") && !pasted.includes("\t")) return;

			e.preventDefault();

			const new_values = pasted
				.split(/[\n\t\r]+/)
				.map((v) => v.trim())
				.filter(Boolean);

			for (const v of new_values) {
				if (!this.values.includes(v)) {
					this.values.push(v);
				}
			}

			this.parse_validate_and_set_in_model("");
			this.refresh_selectable_items();
		});
	}

	open_dropdown() {
		this.$list_wrapper.addClass("show");
		this.$list_wrapper.find(".dropdown-menu").addClass("show");
		this.set_options().then(() => {
			this.set_selectable_items(this.merge_selected(this._options));
		});
		this.adjust_dropdown_right_position();
	}

	close_dropdown() {
		this.$list_wrapper.removeClass("show");
		this.$list_wrapper.find(".dropdown-menu").removeClass("show");
	}

	show_summary() {
		let text;
		if (!this.values || this.values.length === 0) {
			text = "";
		} else if (this.values.length === 1) {
			let val = this.values[0];
			let option = (this._options || []).find((opt) => opt.value === val);
			text = option ? option.label : val;
		} else {
			text = __("{0} values selected", [this.values.length]);
		}
		this.$input.val(text);
		this.$input.attr("placeholder", this.df.placeholder || "");
	}

	refresh_selectable_items() {
		if (this.$list_wrapper.hasClass("show")) {
			let txt = this.$input.val() || "";
			if (txt) {
				let filtered = this._options.filter((opt) => {
					return (
						Awesomplete.FILTER_CONTAINS(opt.label, txt) ||
						Awesomplete.FILTER_CONTAINS(opt.value, txt) ||
						Awesomplete.FILTER_CONTAINS(opt.description, txt)
					);
				});
				this.set_selectable_items(this.merge_selected(filtered));
			} else {
				this.set_selectable_items(this.merge_selected(this._options));
			}
		}
		this.update_status();
	}

	set_input_attributes() {
		this.$list_wrapper
			.attr("data-fieldtype", this.df.fieldtype)
			.attr("data-fieldname", this.df.fieldname);

		this.show_summary();

		if (this.doctype) {
			this.$list_wrapper.attr("data-doctype", this.doctype);
		}
		if (this.df.input_css) {
			this.$list_wrapper.css(this.df.input_css);
		}
		if (this.df.input_class) {
			this.$list_wrapper.addClass(this.df.input_class);
		}
	}

	clear_all_selections() {
		this.values = [];
		this._selected_values = [];
		this.parse_validate_and_set_in_model("");
		this.refresh_selectable_items();
	}

	select_all_options() {
		this.values = this._options.map((opt) => opt.value);
		this._selected_values = this._options.slice();
		this.parse_validate_and_set_in_model("");
		this.refresh_selectable_items();
	}

	toggle_select_item($selectable_item) {
		$selectable_item.toggleClass("selected");
		let value = decodeURIComponent($selectable_item.data().value);

		if ($selectable_item.hasClass("selected")) {
			this.values = this.values.slice();
			this.values.push(value);
		} else {
			this.values = this.values.filter((val) => val !== value);
		}
		this.update_selected_values(value);
		this.parse_validate_and_set_in_model("");
		this.refresh_selectable_items();
	}

	set_value(value) {
		if (!value) return Promise.resolve();
		if (typeof value === "string") {
			value = [value];
		}
		this.values = value;
		this.values.forEach((value) => {
			this.update_selected_values(value);
		});
		this.parse_validate_and_set_in_model("");
		if (!this._focused) {
			this.show_summary();
		}
		return Promise.resolve();
	}

	update_selected_values(value) {
		this._selected_values = this._selected_values || [];
		let option = this._options.find((opt) => opt.value === value);
		if (option) {
			if (this.values.includes(value)) {
				this._selected_values.push(option);
			} else {
				this._selected_values = this._selected_values.filter((opt) => opt.value !== value);
			}
		}
	}

	update_status() {
		if (!this._focused) {
			this.show_summary();
		}
	}

	set_options() {
		let promise = Promise.resolve();

		function process_options(options) {
			return options.map((option) => {
				if (typeof option === "string") {
					return {
						label: option,
						value: option,
					};
				}
				if (!option.label) {
					option.label = option.value;
				}
				return option;
			});
		}

		if (this.df.get_data) {
			let txt = this.$input.val() || "";
			let value = this.df.get_data(txt);
			if (!value) {
				this._options = [];
			} else if (value.then) {
				promise = value.then((options) => {
					this._options = process_options(options);
				});
			} else {
				this._options = process_options(value);
			}
		} else {
			this._options = process_options(this.df.options || []);
		}
		return promise;
	}

	set_selectable_items(options) {
		// Sort: selected values on top
		options = options.slice().sort((a, b) => {
			let a_sel = this.values.includes(a.value) ? 0 : 1;
			let b_sel = this.values.includes(b.value) ? 0 : 1;
			return a_sel - b_sel;
		});

		let html = options
			.map((option) => {
				let encoded_value = encodeURIComponent(option.value);
				let selected = this.values.includes(option.value) ? "selected" : "";
				return `<li class="selectable-item ${selected}" data-value="${encoded_value}">
				<div>
					<strong>${option.label}</strong>
					<div class="small">${option.description}</div>
				</div>
				<div class="multiselect-check">${frappe.utils.icon("tick", "xs")}</div>
			</li>`;
			})
			.join("");
		if (!html) {
			html = `<li class="text-muted">${__("No values to show")}</li>`;
		}
		this.$list_wrapper.find(".selectable-items").html(html);

		// auto-highlight first unselected item
		this.highlighted = -1;
		this._$last_highlighted = null;
		let $first_unselected = this.$list_wrapper.find(".selectable-item:not(.selected)").first();
		if ($first_unselected.length) {
			let $items = this.$list_wrapper.find(".selectable-item");
			this.highlighted = $items.index($first_unselected);
			this._$last_highlighted = $first_unselected.addClass("highlighted");
		}
	}

	adjust_dropdown_right_position() {
		setTimeout(() => {
			const $dropdown = $(this.$list_wrapper).find("ul.dropdown-menu");

			const dropdown_el = $dropdown[0];
			const parent_el = dropdown_el.parentElement;
			const dropdown_rect = dropdown_el.getBoundingClientRect();

			const page_left_position =
				parent_el?.parentElement?.parentElement?.getBoundingClientRect()?.left;

			if (page_left_position && dropdown_rect.left - page_left_position <= 100) return;

			const parent_rect = parent_el.getBoundingClientRect();
			const right_diff = parent_rect.right - dropdown_rect.right;
			dropdown_el.style.left = `${right_diff}px`;
		}, 20);
	}

	get_value() {
		return this.values;
	}

	highlight_item(value) {
		this.highlighted += value;

		if (this.highlighted < 0) {
			this.highlighted = 0;
		}
		let $items = this.$list_wrapper.find(".selectable-item");
		if (this.highlighted > $items.length - 1) {
			this.highlighted = $items.length - 1;
		}

		let $item = $items[this.highlighted];

		if (this._$last_highlighted) {
			this._$last_highlighted.removeClass("highlighted");
		}
		this._$last_highlighted = $($item).addClass("highlighted");
		this.scroll_dropdown_if_needed($item);
	}

	scroll_dropdown_if_needed($item) {
		if ($item.scrollIntoView) {
			$item.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
		} else {
			$item.parentNode.scrollTop = $item.offsetTop - $item.parentNode.offsetTop;
		}
	}
};
