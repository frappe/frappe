frappe.ui.form.ControlSignature = class ControlSignature extends frappe.ui.form.ControlData {
	make() {
		var me = this;
		this.saving = false;
		this.loading = false;
		super.make();

		if (this.df.label) {
			$(this.wrapper).find("label").text(__(this.df.label, null, this.df.parent));
		}
		this.set_doc_url();

		frappe.require("/assets/frappe/js/lib/jSignature.min.js").then(() => {
			// make jSignature field
			me.body = $('<div class="signature-field"></div>').prependTo(me.$input_wrapper);

			new ResizeObserver(() => me.make_pad()).observe(me.body[0]);
		});

		this.img_wrapper = $(`<div class="signature-display">
			<div class="missing-image attach-missing-image">
				${frappe.utils.icon("restriction", "md")}</i>
			</div></div>`).prependTo(this.$input_wrapper);
		this.img = $("<img class='img-responsive attach-image-display'>")
			.appendTo(this.img_wrapper)
			.toggle(false);
	}

	make_pad() {
		let width = this.body.width();
		if (width > 0 && !this.$pad) {
			this.$pad = this.body
				.jSignature({
					height: 200,
					color: "var(--text-color)",
					decorColor: "black",
					width,
					lineWidth: 2,
					backgroundColor: "var(--control-bg)",
				})
				.on("change", this.on_save_sign.bind(this));
			this.load_pad();
			this.$reset_button_wrapper = $(`
					<div class="signature-btn-row">
						<a href="#" type="button" class="signature-reset btn icon-btn">
							${frappe.utils.icon("es-line-reload", "sm")}
						</a>
					</div>
				`)
				.appendTo(this.$pad)
				.on("click", ".signature-reset", () => {
					this.on_reset_sign();
					return false;
				});
			this.refresh_input();
		}
	}
	refresh_input() {
		// signature dom is not ready
		if (!this.body) return;
		// prevent to load the second time
		this.make_pad();
		this.$wrapper.find(".control-input").toggle(false);
		this.set_editable(this.get_status() == "Write");
		this.load_pad();
		if (this.get_status() == "Read") {
			$(this.disp_area).toggle(false);
		}
	}
	set_image(value) {
		if (value) {
			$(this.img_wrapper).find(".missing-image").toggle(false);
			this.img.attr("src", value).toggle(true);
		} else {
			$(this.img_wrapper).find(".missing-image").toggle(true);
			this.img.toggle(false);
		}
	}
	load_pad() {
		// make sure not triggered during saving
		if (this.saving) return;
		// get value
		var value = this.get_value();
		// import data for pad
		if (this.$pad) {
			this.loading = true;
			// reset in all cases
			this.$pad.jSignature("reset");
			if (value) {
				// load the image to find out the size, because scaling will affect
				// stroke width
				try {
					this.$pad.jSignature("setData", value);
					this.set_image(value);
				} catch (e) {
					console.log("Cannot set data for signature", value, e);
				}
			}

			this.loading = false;
		}
	}
	set_editable(editable) {
		this.$pad && this.$pad.toggle(editable);
		this.img_wrapper.toggle(!editable);
		if (this.$reset_button_wrapper) {
			this.$reset_button_wrapper.toggle(editable);
			if (editable) {
				this.$reset_button_wrapper.addClass("editing");
			} else {
				this.$reset_button_wrapper.removeClass("editing");
			}
		}
	}
	set_my_value(value) {
		if (this.saving || this.loading) return;
		this.saving = true;
		this.set_value(value);
		this.saving = false;
	}
	get_value() {
		return this.value ? this.value : this.get_model_value();
	}
	// reset signature canvas
	on_reset_sign() {
		this.$pad.jSignature("reset");
		this.set_my_value("");
	}
	// save signature value to model and display
	on_save_sign() {
		if (this.saving || this.loading) return;
		var base64_img = this.$pad.jSignature("getData");
		this.set_my_value(base64_img);
		this.set_image(this.get_value());
	}
	on_section_collapse() {
		this.refresh();
	}
};
