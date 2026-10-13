import Picker from "../../color_picker/color_picker";

frappe.ui.form.ControlColor = class ControlColor extends frappe.ui.form.ControlData {
	make_input() {
		this.df.placeholder = __(this.df.placeholder) || __("Choose a color");
		super.make_input();
		this.make_color_input();
	}

	make_color_input() {
		let picker_wrapper = $("<div>");
		this.picker = new Picker({
			parent: picker_wrapper[0],
			color: this.get_color(),
			swatches: [
				"#171717",
				"#7c7c7c",
				"#ce2c2c",
				"#d35a09",
				"#ca7e0c",
				"#ab790d",
				"#268c5c",
				"#0a857b",
				"#1f8cad",
				"#077ddf",
				"#6e57d1",
				"#8e49ca",
				"#cf3a96",
			],
		});

		this.$wrapper
			.popover({
				trigger: "manual",
				offset: "0, 4",
				boundary: "viewport",
				placement: "bottom",
				template: `
				<div class="popover color-picker-popover">
					<div class="picker-arrow arrow"></div>
					<div class="popover-body popover-content"></div>
				</div>
			`,
				content: () => picker_wrapper,
				html: true,
			})
			.on("shown.bs.popover", () => {
				const color = this.get_color();
				if (color) this.picker.set_color(color);
				this.picker.refresh();
			})
			.on("hidden.bs.popover", () => {
				$("body").off("click.color-popover");
				$(window).off("hashchange.color-popover");
			});

		this.picker.on_change = (color) => {
			this.set_value(color);
		};

		if (!this.selected_color) {
			this.selected_color = $(`<div class="selected-color"></div>`);
			this.selected_color.insertAfter(this.$input);
		}

		this.$wrapper
			.find(".selected-color")
			.parent()
			.on("click", (e) => {
				this.$wrapper.popover("toggle");
				if (!this.get_color()) {
					this.$input.val("");
				}
				e.stopPropagation();
				$("body").on("click.color-popover", (ev) => {
					if (!$(ev.target).parents().is(".popover")) {
						this.$wrapper.popover("hide");
					}
				});
				$(window).on("hashchange.color-popover", () => {
					this.$wrapper.popover("hide");
				});
			});
	}

	refresh() {
		super.refresh();
		let color = this.get_color();
		if (this.picker && this.picker.color !== color) {
			this.picker.color = color;
			this.picker.refresh();
		}
	}

	set_formatted_input(value) {
		super.set_formatted_input(value);
		this.$input?.val(value);
		this.selected_color?.css({
			"background-color": value || "transparent",
		});
		this.selected_color?.toggleClass("no-value", !value);
	}

	get_color() {
		return this.validate(this.get_value());
	}

	validate(value) {
		if (value === "") {
			return "";
		}
		var is_valid = /^#[0-9A-F]{6}$/i.test(value);
		if (is_valid) {
			return value;
		}
		return null;
	}
};
