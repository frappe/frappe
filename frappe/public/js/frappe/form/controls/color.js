frappe.ui.form.ControlColor = frappe.ui.form.ControlData.extend({
	make_input: function () {
		this._super();
		this.colors = [
			"#ffc4c4", "#ff8989", "#ff4d4d", "#a83333",
			"#ffe8cd", "#ffd19c", "#ffb868", "#a87945",
			"#ffd2c2", "#ffa685", "#ff7846", "#a85b5b",
			"#ffd7d7", "#ffb1b1", "#ff8989", "#a84f2e",
			"#fffacd", "#fff168", "#fff69c", "#a89f45",
			"#ebf8cc", "#d9f399", "#c5ec63", "#7b933d",
			"#cef6d1", "#9deca2", "#6be273", "#428b46",
			"#d2f8ed", "#a4f3dd", "#77ecca", "#49937e",
			"#d2f1ff", "#a6e4ff", "#78d6ff", "#4f8ea8",
			"#d2d2ff", "#a3a3ff", "#7575ff", "#4d4da8",
			"#dac7ff", "#b592ff", "#8e58ff", "#5e3aa8",
			"#f8d4f8", "#f3aaf0", "#ec7dea", "#934f92"
		];
		this.make_color_input();
	},
	make_color_input: function () {
		this.$wrapper
			.find('.control-input-wrapper')
			.append(`<div class="color-picker">
				<div class="color-picker-pallete"></div>
			</div>`);
		this.$color_pallete = this.$wrapper.find('.color-picker-pallete');

		var color_html = this.colors.map(this.get_color_box).join("");
		this.$color_pallete.append(color_html);
		this.$color_pallete.hide();
		this.bind_events();
	},
	get_color_box: function (hex) {
		return `<div class="color-box" data-color="${hex}" style="background-color: ${hex}"></div>`;
	},
	set_formatted_input: function(value) {
		this._super(value);

		if (!value) value = '#FFFFFF';
		const contrast    = frappe.ui.color.get_contrast_color(value);

		this.$input.css({
			"background-color": value, "color": contrast
		});
	},
	bind_events: function () {
		var mousedown_happened = false;
		this.$wrapper.on("click", ".color-box", (e) => {
			mousedown_happened = false;

			var color_val = $(e.target).data("color");
			this.set_value(color_val);
			// set focus so that we can blur it later
			this.set_focus();
		});

		this.$wrapper.find(".color-box").mousedown(() => {
			mousedown_happened = true;
		});

		this.$input.on("focus", () => {
			this.$color_pallete.show();
		});
		this.$input.on("blur", () => {
			if (mousedown_happened) {
				// cancel the blur event
				mousedown_happened = false;
			} else {
				// blur event is okay
				$(this.$color_pallete).hide();
			}
		});
	},
	validate: function (value) {
		if(value === '') {
			return '';
		}
		var is_valid = /^#[0-9A-F]{6}$/i.test(value);
		if(is_valid) {
			return value;
		}
		frappe.msgprint(__("{0} is not a valid hex color", [value]));
		return null;
	}
});
