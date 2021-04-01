frappe.ui.form.ControlDuration = frappe.ui.form.ControlData.extend({
	make_input: function() {
		this._super();
		this.make_picker();
	},

	make_picker: function() {
		this.inputs = [];
		this.set_duration_options();
		this.$picker = $(
			`<div class="duration-picker">
				<div class="picker-row row"></div>
			</div>`
		);
		this.$wrapper.append(this.$picker);
		this.build_numeric_input("days", this.duration_options.hide_days);
		this.build_numeric_input("hours", false);
		this.build_numeric_input("minutes", false);
		this.build_numeric_input("seconds", this.duration_options.hide_seconds);
		this.set_duration_picker_value(this.value);
		this.$picker.hide();
		this.bind_events();
		this.refresh();
	},

	build_numeric_input: function(label, hidden, max) {
		let $duration_input = $(`
			<input class="input-sm duration-input" data-duration="${label}" type="number" min="0" value="0">
		`);

		let $input = $(`<div class="row duration-row"></div>`).prepend($duration_input);

		if (max) {
			$duration_input.attr("max", max);
		}

		this.inputs[label] = $duration_input;

		let $control = $(`
			<div class="col duration-col">
				<div class="row duration-row duration-label">${__(label)}</div>
			</div>`
		);

		if (hidden) {
			$control.addClass("hidden");
		}
		$control.prepend($input);
		$control.appendTo(this.$picker.find(".picker-row"));
	},

	set_duration_options() {
		this.duration_options = frappe.utils.get_duration_options(this.df);
	},

	set_duration_picker_value: function(value) {
		let total_duration = frappe.utils.seconds_to_duration(value, this.duration_options);

		if (this.$picker) {
			Object.keys(total_duration).forEach(duration => {
				this.inputs[duration].prop("value", total_duration[duration]);
			});
		}
	},

	bind_events: function() {
		// flag to handle the display property of the picker
		let clicked = false;

		this.$wrapper.find(".duration-input").mousedown(() => {
			// input in individual duration boxes
			clicked = true;
		});

		this.$picker.on("change", ".duration-input", () => {
			// duration changed in individual boxes
			clicked = false;
			let duration = this.get_duration();
			let value = frappe.utils.duration_to_seconds(
				duration.days,
				duration.hours,
				duration.minutes,
				duration.seconds
			);
			this.set_value(value);
			this.set_focus();
		});

		this.$input.on("focus", () => {
			this.$picker.show();
			let is_picker_set = this.is_duration_picker_set(this.inputs);
			if (!is_picker_set) {
				this.set_duration_picker_value(this.value);
			}
		});

		this.$input.on("blur", () => {
			// input in duration boxes, don't close the picker
			if (clicked) {
				clicked = false;
			} else {
				// blur event was not due to duration inputs
				this.$picker.hide();
			}
		});
	},

	get_value() {
		return cint(this.value);
	},

	refresh_input: function() {
		this._super();
		this.set_duration_options();
		this.set_duration_picker_value(this.value);
	},

	format_for_input: function(value) {
		return frappe.utils.get_formatted_duration(value, this.duration_options);
	},

	get_duration() {
		// returns an object of days, hours, minutes and seconds from the inputs array
		let total_duration = {
			minutes: 0,
			hours: 0,
			days: 0,
			seconds: 0
		};
		if (this.inputs) {
			total_duration.minutes = parseInt(this.inputs.minutes.val());
			total_duration.hours = parseInt(this.inputs.hours.val());
			if (!this.duration_options.hide_days) {
				total_duration.days = parseInt(this.inputs.days.val());
			}
			if (!this.duration_options.hide_seconds) {
				total_duration.seconds = parseInt(this.inputs.seconds.val());
			}
		}
		return total_duration;
	},

	is_duration_picker_set(inputs) {
		let is_set = false;
		Object.values(inputs).forEach(duration => {
			if (duration.prop("value") != 0) {
				is_set = true;
			}
		});
		return is_set;
	}
});