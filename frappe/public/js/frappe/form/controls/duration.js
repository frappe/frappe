frappe.ui.form.ControlDuration = class ControlDuration extends frappe.ui.form.ControlData {
	make_input() {
		super.make_input();
		this.make_picker();
	}

	validate(value) {
		if (!value) {
			return null;
		}
		return super.validate(value);
	}

	make_picker() {
		this.inputs = [];
		this.set_duration_options();
		this.$picker = $(
			`<div class="duration-picker">
				<div class="picker-row row"></div>
			</div>`
		);
		this.$wrapper.append(this.$picker);
		this.build_numeric_input(
			"days",
			this.duration_options.hide_days,
			0,
			__("Days", null, "Duration")
		);
		this.build_numeric_input("hours", false, 0, __("Hours", null, "Duration"));
		this.build_numeric_input("minutes", false, 0, __("Minutes", null, "Duration"));
		this.build_numeric_input(
			"seconds",
			this.duration_options.hide_seconds,
			0,
			__("Seconds", null, "Duration")
		);
		this.set_duration_picker_value(this.value);
		this.$picker.hide();
		this.bind_events();
		this.refresh();
	}

	build_numeric_input(name, hidden, max, label) {
		let $duration_input = $(`
			<input class="input-sm duration-input" data-duration="${name}" type="number" min="0" value="0">
		`);

		let $input = $(`<div class="row duration-row"></div>`).prepend($duration_input);

		if (max) {
			$duration_input.attr("max", max);
		}

		this.inputs[name] = $duration_input;

		let $control = $(`
			<div class="col duration-col">
				<div class="row duration-row duration-label">${label}</div>
			</div>`);

		if (hidden) {
			$control.addClass("hidden");
		}
		$control.prepend($input);
		$control.appendTo(this.$picker.find(".picker-row"));
	}

	set_duration_options() {
		this.duration_options = frappe.utils.get_duration_options(this.df);
	}

	set_duration_picker_value(value) {
		let total_duration = frappe.utils.seconds_to_duration(value || 0, this.duration_options);

		if (this.$picker) {
			Object.keys(total_duration).forEach((duration) => {
				this.inputs[duration].prop("value", total_duration[duration]);
			});
		}
	}

	bind_events() {
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
			this.set_formatted_input(this.value);
		});
	}

	get_value() {
		return cint(this.value);
	}

	parse(value) {
		if (!value) {
			return "";
		} else if (/^\s*\d+\s*$/.test(value)) {
			return parseInt(value);
		}

		this.DURATION_PARSE_REGEX ??= makeDurationParseRegex();
		const match = String(value).trim().match(this.DURATION_PARSE_REGEX);

		if (!match?.groups || !Object.values(match.groups).some((g) => !!g)) {
			return null; // At least one group is required
		}

		let duration_in_seconds = 0;
		for (const [key, multiplier] of Object.entries(DURATION_MULTIPLIERS)) {
			duration_in_seconds += parseInt(match.groups?.[key] || 0) * multiplier;
		}
		return duration_in_seconds;
	}

	set_formatted_input(value) {
		super.set_formatted_input(value);
		this.set_duration_picker_value(value);
	}

	refresh_input() {
		super.refresh_input();
		this.set_duration_options();
		this.set_duration_picker_value(this.value);
	}

	format_for_input(value) {
		return frappe.utils.get_formatted_duration(value, this.duration_options);
	}

	get_duration() {
		// returns an object of days, hours, minutes and seconds from the inputs array
		let total_duration = {
			minutes: 0,
			hours: 0,
			days: 0,
			seconds: 0,
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
	}

	is_duration_picker_set(inputs) {
		let is_set = false;
		Object.values(inputs).forEach((duration) => {
			if (duration.prop("value") != 0) {
				is_set = true;
			}
		});
		return is_set;
	}
};

const DURATION_MULTIPLIERS = {
	weeks: 7 * 24 * 60 * 60,
	days: 24 * 60 * 60,
	hours: 60 * 60,
	minutes: 60,
	seconds: 1,
};

function makeDurationParseRegex() {
	// Wrap in a function for translations to work
	// Matches strings like: 1d 2h 3m 4s, with optional parts

	const _part = (key, seps) => {
		// Use named capture group for the key, then match the separator (h, m, s)
		const rCapture = `(?<${key}>\\d+)`;
		const rSep = "(?:" + seps.join("|") + ")";
		return "\\s*(?:" + rCapture + "\\s*" + rSep + ")?\\s*";
	};

	return new RegExp(
		[
			_part("days", [__("d", null, "Days (Field: Duration)")]),
			_part("hours", [__("h", null, "Hours (Field: Duration)")]),
			_part("minutes", [__("m", null, "Minutes (Field: Duration)")]),
			_part("seconds", [__("s", null, "Seconds (Field: Duration)")]),
			".*", // Fallback to ignore unknown parts
		].join(""),
		"i"
	);
}
