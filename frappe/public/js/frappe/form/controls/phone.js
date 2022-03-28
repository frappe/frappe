
import PhonePicker from '../../phone_picker/phone_picker';

frappe.ui.form.ControlPhone = class ControlPhone extends frappe.ui.form.ControlData {

	make_input() {
		super.make_input();
		this.make_icon_input();
		this.input_events();
	}

	input_events() {
		// Replaces code when selected and removes previously selected.
		this.picker.on_change = (country) => {
			const country_code = frappe.boot.country_codes[country].code;
			const country_isd = frappe.boot.country_codes[country].isd;
			this.change_flag(country_code);
			this.$icon = this.selected_icon.find('svg');
			this.$flag = this.selected_icon.find('img');

			if (!this.$icon.hasClass('hide')) {
				this.$icon.toggleClass('hide');
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
				this.set_formatted_input(this.get_country(country) +'-'+ this.$input.val());
			}
			this.change_padding();
		};

		this.$wrapper.find('.selected-phone').on('click', (e) => {
			this.$wrapper.popover('toggle');
			e.stopPropagation();

			$('body').on('click.phone-popover', (ev) => {
				if (!$(ev.target).parents().is('.popover')) {
					this.$wrapper.popover('hide');
				}
			});
			$(window).on('hashchange.phone-popover', () => {
				this.$wrapper.popover('hide');
			});
		});
	}

	make_icon_input() {
		let picker_wrapper = $('<div>');
		this.picker = new PhonePicker({
			parent: picker_wrapper,
			countries: frappe.boot.country_codes
		});

		this.$wrapper.popover({
			trigger: 'manual',
			offset: `${-this.$wrapper.width() / 4.5}, 5`,
			boundary: 'viewport',
			placement: 'bottom',
			template: `
				<div class="popover phone-picker-popover">
					<div class="picker-arrow arrow"></div>
					<div class="popover-body popover-content"></div>
				</div>
			`,
			content: () => picker_wrapper,
			html: true
		}).on('show.bs.popover', () => {
			setTimeout(() => {
				this.picker.refresh();
			}, 10);
		}).on('hidden.bs.popover', () => {
			$('body').off('click.phone-popover');
			$(window).off('hashchange.phone-popover');
		});

		// Default icon when nothing is selected.
		this.selected_icon = this.$wrapper.find('.selected-phone');
		let input_value = this.get_input_value();
		if (!this.selected_icon.length) {
			this.selected_icon = $(`<div class="selected-phone">${frappe.utils.icon("down", "sm")}</div>`);
			this.selected_icon.insertAfter(this.$input);
			this.selected_icon.append($(`<span class= "country"></span>`));
			this.$isd = this.selected_icon.find('.country');
			if (input_value && input_value.split("-").length == 2) {
				this.$isd.text(this.value.split("-")[0]);
			}
		}
	}

	refresh() {
		super.refresh();

		// Previously opened doc values get fetched.
		if (!this.value) {
			this.$input.val("");
			this.$wrapper.find('.country').text("");
			if (this.selected_icon.find('svg').hasClass('hide')) {
				this.selected_icon.find('svg').toggleClass('hide');
				this.selected_icon.find('img').addClass('hide');
			}
			this.$input.css("padding-left", 30);
		}
		if (this.value && this.value.split("-").length == 2) {
			let isd = this.value.split("-")[0];
			this.get_country_code_and_change_flag(isd);
			this.picker.set_country(isd);
			this.picker.refresh();
			if (this.picker.country && this.picker.country !== this.$isd.text()) {
				this.$isd.length && this.$isd.text(isd);
			}
		}
	}


	set_formatted_input(value) {
		if (value && value.includes('-')) {
			this.set_model_value(value);
			this.$input.val(value.split("-").pop());
		} else if (this.$isd.text().trim() && this.value) {
			let code_number = this.$isd.text() + '-' + value;
			this.set_model_value(code_number);
		}
	}

	change_flag(country_code) {
		this.selected_icon.find('img').attr('src', 'https://flagcdn.com/'+country_code+'.svg');
		this.$icon = this.selected_icon.find('img');
		this.$icon.hasClass('hide') && this.$icon.toggleClass('hide');
	}

	// country_code for India is 'in'
	get_country_code_and_change_flag(isd) {
		let country_data = frappe.boot.country_codes;
		let flag = this.selected_icon.find('img');
		for (const country in country_data) {
			if (Object.values(country_data[country]).includes(isd)) {
				let code = country_data[country].code;
				flag = this.selected_icon.find('img');
				if (!flag.length) {
					this.selected_icon.prepend(this.get_country_flag(country));
					this.selected_icon.find('svg').addClass('hide');
				} else {
					this.change_flag(code);
				}
			}
		}
	}
	get_country(country) {
		const country_codes = frappe.boot.country_codes;
		return country_codes[country].isd;
	}
	get_country_flag(country) {
		const country_codes = frappe.boot.country_codes;
		let code = country_codes[country].code;
		return frappe.utils.flag(code);
	}
	change_padding() {
		let len = this.$isd.text().length;
			let diff = len - 3;
			if (len > 3) {
				this.$input.css("padding-left", 67 + (diff * 7));
			} else {
				this.$input.css("padding-left", 67);
			}
		}
};
