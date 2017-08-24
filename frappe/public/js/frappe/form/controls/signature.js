
frappe.ui.form.ControlSignature = frappe.ui.form.ControlData.extend({
	saving: false,
	loading: false,
	make: function() {
		var me = this;
		this._super();

		// make jSignature field
		this.$pad = $('<div class="signature-field"></div>')
			.appendTo(me.wrapper)
			.jSignature({height:300, width: "100%", "lineWidth": 0.8})
			.on('change', this.on_save_sign.bind(this));

		this.img_wrapper = $(`<div class="signature-display">
			<div class="missing-image attach-missing-image">
				<i class="octicon octicon-circle-slash"></i>
			</div></div>`)
			.appendTo(this.wrapper);
		this.img = $("<img class='img-responsive attach-image-display'>")
			.appendTo(this.img_wrapper).toggle(false);


		this.$btnWrapper = $(`<div class="signature-btn-row">
			<a href="#" type="button" class="signature-reset btn btn-default">
			<i class="glyphicon glyphicon-repeat"></i></a>`)
			.appendTo(this.$pad)
			.on("click", '.signature-reset', function() {
				me.on_reset_sign();
				return false;
			});
	},
	refresh_input: function() {
		// prevent to load the second time
		this.$wrapper.find(".control-input").toggle(false);
		this.set_editable(this.get_status()=="Write");
		this.load_pad();
		if(this.get_status()=="Read") {
			$(this.disp_area).toggle(false);
		}
	},
	set_image: function(value) {
		if(value) {
			$(this.img_wrapper).find(".missing-image").toggle(false);
			this.img.attr("src", value).toggle(true);
		} else {
			$(this.img_wrapper).find(".missing-image").toggle(true);
			this.img.toggle(false);
		}
	},
	load_pad: function() {
		// make sure not triggered during saving
		if (this.saving) return;
		// get value
		var value = this.get_value();
		// import data for pad
		if (this.$pad) {
			this.loading = true;
			// reset in all cases
			this.$pad.jSignature('reset');
			if (value) {
				// load the image to find out the size, because scaling will affect
				// stroke width
				try {
					this.$pad.jSignature('setData', value);
					this.set_image(value);
				}
				catch (e){
					// eslint-disable-next-line
					console.log("Cannot set data for signature", value, e);
				}
			}

			this.loading = false;
		}
	},
	set_editable: function(editable) {
		this.$pad.toggle(editable);
		this.img_wrapper.toggle(!editable);
		this.$btnWrapper.toggle(editable);
		if (editable) {
			this.$btnWrapper.addClass('editing');
		}
		else {
			this.$btnWrapper.removeClass('editing');
		}
	},
	set_my_value: function(value) {
		if (this.saving || this.loading) return;
		this.saving = true;
		this.set_value(value);
		this.value = value;
		this.saving = false;
	},
	get_value: function() {
		return this.value? this.value: this.get_model_value();
	},
	// reset signature canvas
	on_reset_sign: function() {
		this.$pad.jSignature("reset");
		this.set_my_value("");
	},
	// save signature value to model and display
	on_save_sign: function() {
		if (this.saving || this.loading) return;
		var base64_img = this.$pad.jSignature("getData");
		this.set_my_value(base64_img);
		this.set_image(this.get_value());
	}
});
