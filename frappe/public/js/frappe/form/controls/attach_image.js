frappe.ui.form.ControlAttachImage = frappe.ui.form.ControlAttach.extend({
	make: function() {
		var me = this;
		this._super();

		this.container = $('<div class="control-container">').insertAfter($(this.wrapper));
		$(this.wrapper).detach();
		this.container.attr('data-fieldtype', this.df.fieldtype).append(this.wrapper);
		if(this.df.align === 'center') {
			this.container.addClass("flex-justify-center");
		} else if (this.df.align === 'right') {
			this.container.addClass("flex-justify-end");
		}

		this.img_wrapper = $('<div style="width: 100%; height: calc(100% - 40px); position: relative;">\
			<div class="missing-image attach-missing-image"><i class="octicon octicon-device-camera"></i></div></div>')
			.appendTo(this.wrapper);

		this.img_container = $(`<div class='img-container'></div>`);
		this.img = $(`<img class='img-responsive attach-image-display'>`)
			.appendTo(this.img_container);

		this.img_overlay = $(`<div class='img-overlay'>
				<span class="overlay-text">Change</span>
			</div>`).appendTo(this.img_container);

		this.remove_image_link = $('<a style="font-size: 12px;color: #8D99A6;">Remove</a>');

		this.img_wrapper.append(this.img_container).append(this.remove_image_link);
		// this.img.toggle(false);
		// this.img_overlay.toggle(false);
		this.img_container.toggle(false);
		this.remove_image_link.toggle(false);

		// propagate click to Attach button
		this.img_wrapper.find(".missing-image").on("click", function() { me.$input.click(); });
		this.img_container.on("click", function() { me.$input.click(); });
		this.remove_image_link.on("click", function() { me.$value.find(".close").click(); });

		this.set_image();
	},
	refresh_input: function() {
		this._super();
		$(this.wrapper).find('.btn-attach').addClass('hidden');
		this.set_image();
		if(this.get_status()=="Read") {
			$(this.disp_area).toggle(false);
		}
	},
	set_image: function() {
		if(this.get_value()) {
			$(this.img_wrapper).find(".missing-image").toggle(false);
			// this.img.attr("src", this.dataurl ? this.dataurl : this.value).toggle(true);
			// this.img_overlay.toggle(true);
			this.img.attr("src", this.dataurl ? this.dataurl : this.value);
			this.img_container.toggle(true);
			this.remove_image_link.toggle(true);
		} else {
			$(this.img_wrapper).find(".missing-image").toggle(true);
			// this.img.toggle(false);
			// this.img_overlay.toggle(false);
			this.img_container.toggle(false);
			this.remove_image_link.toggle(false);
		}
	}
});
