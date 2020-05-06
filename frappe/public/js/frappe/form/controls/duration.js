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
		this.build_numeric_input("days", !this.duration_options.showDays);
		this.build_numeric_input("hrs", false);
		this.build_numeric_input("mins", false);
		this.build_numeric_input("secs", !this.duration_options.showSeconds);
		this.set_duration_picker();
		this.$picker.hide();
		this.bind_events();
		this.refresh();
	},

	build_numeric_input: function(label, hidden, max) {
		let $duration_input = $(`
			<input class="input-sm duration-input" data-duration="${label}" type="number" min="0" value="0">
		`)

		let $input = $(`<div class="row duration-row"></div>`).prepend($duration_input);

		if (max) {
			$duration_input.attr("max", max);
		}

		this.inputs[label] = $duration_input;

		let $control = $(`
			<div class="col duration-col">
				<div class="row duration-row duration-label">${label}</div>
			</div>`
		)

		if (hidden) {
			$control.addClass("hidden");
		}
		$control.prepend($input);
		$control.appendTo(this.$picker.find(".picker-row"));
	},

	set_duration_options() {
		this.duration_options = frappe.meta.get_duration_options(this.df, this.get_doc());
	},

	set_duration_picker() {
		let total_duration = frappe.utils.seconds_to_duration(this.value, this.duration_options);

		if (total_duration.days) {
			this.$picker.find(`[data-duration="days"]`).prop("value", total_duration.days);
		}
		if (total_duration.hours) {
			this.$picker.find(`[data-duration="hrs"]`).prop("value", total_duration.hours);
		}
		if (total_duration.minutes) {
			this.$picker.find(`[data-duration="mins"]`).prop("value", total_duration.minutes);
		}
		if (total_duration.seconds) {
			this.$picker.find(`[data-duration="secs"]`).prop("value", total_duration.seconds);
		}
	},

	bind_events: function() {
		let me = this;
		let clicked = false;

		this.$picker.on("change", ".duration-input", () => {
			clicked = false;
			me.set_value(me.duration_to_seconds());
			me.set_focus();
		});

		this.$wrapper.find(".duration-input").mousedown(() => {
			clicked = true;
		});

		this.$input.on("focus", () => {
			this.$picker.show();
		});

		this.$input.on("blur", () => {
			if (clicked) {
				clicked = false;
			} else {
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
		this.set_duration_picker();
	},

	format_for_input: function(value) {
		return frappe.utils.get_formatted_duration(value, this.duration_options);
	},

	duration_to_seconds() {
		let value = 0;
		if (this.inputs) {
			let total_duration = {
				minutes : parseInt(this.inputs.mins.val()),
				hours : parseInt(this.inputs.hrs.val()),
			};
			if (this.duration_options.showDays) {
				total_duration.days = parseInt(this.inputs.days.val());
			}
			if (this.duration_options.showSeconds) {
				total_duration.seconds = parseInt(this.inputs.secs.val());
			}

			if (total_duration.days) {
				value += total_duration.days * 24 * 60 * 60;
			}
			if (total_duration.hours) {
				value += total_duration.hours * 60 * 60;
			}
			if (total_duration.minutes) {
				value += total_duration.minutes * 60;
			}
			if (total_duration.seconds) {
				value += total_duration.seconds;
			}
		}
		return value;
	}
});