frappe.ui.form.ControlPassword = class ControlPassword extends frappe.ui.form.ControlData {
	static input_type = "password";
	make() {
		super.make();
		this.enable_password_checks = true;
	}
	make_input() {
		var me = this;
		super.make_input();

		this.indicator = $(
			`<div class="password-strength-indicator hidden">
				<div class="progress-text"></div>
				<div class="progress">
					<div class="progress-bar" role="progressbar"
						aria-valuenow="0"
						aria-valuemin="0" aria-valuemax="100">
					</div>
				</div>
			</div>`
		).insertAfter(this.$input);

		this.progress_text = this.indicator.find(".progress-text");
		this.progress_bar = this.indicator.find(".progress-bar");
		this.message = this.$wrapper.find(".help-box");

		this.$input.on(
			"keyup",
			frappe.utils.debounce(() => {
				let hide_icon = me.$input.val() && !me.$input.val().includes("*");
				me.toggle_password.toggleClass("hidden", !hide_icon);
				me.get_password_strength(me.$input.val());
			}, 500)
		);

		this.toggle_password = $(`
			<div class="toggle-password hidden">
				${frappe.utils.icon("unhide", "sm")}
			</div>
		`).insertAfter(this.$input);

		this.toggle_password.on("click", () => {
			if (this.$input.attr("type") === "password") {
				this.$input.attr("type", "text");
				this.toggle_password.html(frappe.utils.icon("hide", "sm"));
			} else {
				this.$input.attr("type", "password");
				this.toggle_password.html(frappe.utils.icon("unhide", "sm"));
			}
		});

		!this.value && this.toggle_password.removeClass("hidden");
	}

	disable_password_checks() {
		this.enable_password_checks = false;
	}

	get_password_strength(value) {
		if (!this.enable_password_checks) {
			return;
		}

		if (!value) {
			this.indicator.addClass("hidden");
			this.message.addClass("hidden");
			return;
		}

		var me = this;
		frappe.call({
			type: "POST",
			method: "frappe.core.doctype.user.user.test_password_strength",
			args: {
				new_password: value || "",
			},
			callback: function (r) {
				if (r.message.score !== undefined && r.message.score !== null) {
					const indicators = ["red", "red", "orange", "blue", "green"];
					me.set_strength_indicator(indicators[r.message.score]);
				}
			},
		});
	}
	set_strength_indicator(color) {
		let strength = {
			red: [__("Weak"), "danger", 25],
			orange: [__("Average"), "warning", 50],
			blue: [__("Strong"), "info", 75],
			green: [__("Excellent"), "success", 100],
		};
		let progress_text = strength[color][0];
		let progress_color = strength[color][1];
		let progress_percent = strength[color][2];

		this.indicator.removeClass("hidden");

		this.progress_text.html(progress_text).css("color", `var(--${color}-500)`);

		this.progress_bar
			.css("width", progress_percent + "%")
			.attr("aria-valuenow", progress_percent)
			.removeClass()
			.addClass("progress-bar progress-bar-" + progress_color);

		let message = __("Include symbols, numbers and capital letters in the password");
		this.message.html(message).toggleClass("hidden", color == "green");
	}
};
