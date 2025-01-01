import localforage from "localforage";
import PhonePicker from "../../phone_picker/phone_picker";

frappe.ui.form.ControlPhone = class ControlPhone extends frappe.ui.form.ControlData {
	async make_input() {
		await this.setup_country_codes();
		super.make_input();
		this.setup_country_code_picker();
		this.input_events();
	}

	async setup_country_codes() {
		const key = "country_code_info";
		let data = await localforage.getItem(key);
		if (data) {
			this.country_codes = data;
		} else {
			const data = await frappe.xcall("frappe.geo.country_info.get_country_timezone_info");
			this.country_codes = data?.country_info;
			localforage.setItem(key, this.country_codes);
		}
	}

	input_events() {
		this.$input.keydown((e) => {
			const key_code = e.keyCode;
			if ([frappe.ui.keyCode.BACKSPACE].includes(key_code)) {
				if (this.$input.val().length == 0) {
					this.country_code_picker.reset();
				}
			}
		});

		// Replaces code when selected and removes previously selected.
		this.country_code_picker.on_change = (country) => {
			if (!country) {
				return this.reset_input();
			}
			const country_code = this.country_codes[country].code;
			const country_isd = this.country_codes[country].isd;
			this.set_flag(country_code);
			this.$icon = this.selected_icon.find("svg");
			this.$flag = this.selected_icon.find("img");

			if (!this.$icon.hasClass("hide")) {
				this.$icon.toggleClass("hide");
			}
			if (!this.$flag.length) {
				this.selected_icon.prepend(this.get_country_flag(country));
			}
			if (!this.$isd.length) {
				this.selected_icon.append($(`<span class= "country"> ${country_isd}</span>`));
			} else {
				this.$isd.text(country_isd);
			}
			if (this.$input.val()) {
				this.set_value(this.get_country(country) + "-" + this.$input.val());
			}
			this.update_padding();
			// hide popover and focus input
			this.$wrapper.popover("hide");
			this.$input.focus();
		};

		this.$wrapper.find(".selected-phone").on("click", (e) => {
			this.$wrapper.popover("toggle");
			e.stopPropagation();

			$("body").on("click.phone-popover", (ev) => {
				if (!$(ev.target).parents().is(".popover")) {
					this.$wrapper.popover("hide");
				}
			});
			$(window).on("hashchange.phone-popover", () => {
				this.$wrapper.popover("hide");
			});
		});
	}

	setup_country_code_picker() {
		let picker_wrapper = $("<div>");
		this.country_code_picker = new PhonePicker({
			parent: picker_wrapper,
			countries: this.country_codes,
		});

		this.$wrapper
			.popover({
				trigger: "manual",
				offset: `${-this.$wrapper.width() / 4.5}, 5`,
				boundary: "viewport",
				placement: "bottom",
				template: `
				<div class="popover phone-picker-popover">
					<div class="picker-arrow arrow"></div>
					<div class="popover-body popover-content"></div>
				</div>
			`,
				content: () => picker_wrapper,
				html: true,
			})
			.on("show.bs.popover", () => {
				setTimeout(() => {
					this.country_code_picker.refresh();
					this.country_code_picker.search_input.focus();
				}, 10);
			})
			.on("hidden.bs.popover", () => {
				$("body").off("click.phone-popover");
				$(window).off("hashchange.phone-popover");
			});

		// Default icon when nothing is selected.
		this.selected_icon = this.$wrapper.find(".selected-phone");
		let input_value = this.get_input_value();
		if (!this.selected_icon.length) {
			this.selected_icon = $(
				`<div class="selected-phone">${frappe.utils.icon("down", "sm")}</div>`
			);
			this.selected_icon.insertAfter(this.$input);
			this.selected_icon.append($(`<span class= "country"></span>`));
			this.$isd = this.selected_icon.find(".country");
			if (input_value && input_value.split("-").length == 2) {
				this.$isd.text(this.value.split("-")[0]);
			}
		}
	}

	refresh() {
		super.refresh();
		// Previously opened doc values showing up on a new doc
		// Previously opened doc values showing up on other docs where phone fields is empty

		if (!this.get_value()) {
			this.reset_input();
		}
	}

	reset_input() {
		if (!this.$input) return;
		this.$input.val("");
		this.$wrapper.find(".country").text("");
		if (this.selected_icon.find("svg").hasClass("hide")) {
			this.selected_icon.find("svg").toggleClass("hide");
			this.selected_icon.find("img").addClass("hide");
		}
		this.$input.css("padding-left", 30);
	}

	async set_formatted_input(value) {
		if (!this.country_codes) {
			await this.setup_country_codes();
		}
		if (value && value.includes("-") && value.split("-").length == 2) {
			if (!this.selected_icon.find("svg").hasClass("hide")) {
				this.selected_icon.find("svg").toggleClass("hide");
			}
			let isd = this.value.split("-")[0];
			this.get_country_code_and_change_flag(isd);
			this.country_code_picker.set_country(isd);
			this.country_code_picker.refresh();
			if (
				this.country_code_picker.country &&
				this.country_code_picker.country !== this.$isd.text()
			) {
				this.$isd.length && this.$isd.text(isd);
			}
			this.update_padding();
			this.$input.val(value.split("-").pop());
		} else if (this.$isd.text().trim() && this.value) {
			let code_number = this.$isd.text() + "-" + value;
			this.set_value(code_number);
		}
	}

	get_value() {
		return this.value;
	}

	set_flag(country_code) {
		this.selected_icon.find("img").attr("src", `https://flagcdn.com/${country_code}.svg`);
		this.$icon = this.selected_icon.find("img");
		this.$icon.hasClass("hide") && this.$icon.toggleClass("hide");
	}

	// country_code for India is 'in'
	get_country_code_and_change_flag(isd) {
		let country_data = this.country_codes;
		let flag = this.selected_icon.find("img");
		for (const country in country_data) {
			if (Object.values(country_data[country]).includes(isd)) {
				let code = country_data[country].code;
				flag = this.selected_icon.find("img");
				if (!flag.length) {
					this.selected_icon.prepend(this.get_country_flag(country));
					this.selected_icon.find("svg").addClass("hide");
				} else {
					this.set_flag(code);
				}
			}
		}
	}

	get_country(country) {
		const country_codes = this.country_codes;
		return country_codes[country].isd;
	}

	get_country_flag(country) {
		const country_codes = this.country_codes;
		let code = country_codes[country].code;
		return frappe.utils.flag(code);
	}

	update_padding() {
		let len = this.$isd.text().length;
		let diff = len - 2;
		if (len > 2) {
			this.$input.css("padding-left", 60 + diff * 7);
		} else {
			this.$input.css("padding-left", 60);
		}
	}
};
